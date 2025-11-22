"""
Основной файл сервиса авторизации
"""
import logging
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Cookie
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import urllib.parse

from .config import settings
from .yandex_oauth import yandex_oauth
from .session_manager import session_manager
from .database import db

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Устанавливаем уровень для uvicorn, чтобы не было слишком много логов
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)

app = FastAPI(title="Auth Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_domain_from_request(request: Request) -> str:
    """Получить домен из запроса"""
    host = request.headers.get("host", "")
    # Убираем порт если есть
    domain = host.split(":")[0]
    return domain.lower()


def get_session_from_cookie(request: Request) -> Optional[dict]:
    """Получить сессию из cookie"""
    session_token = request.cookies.get(settings.session_cookie_name)
    logger.debug(f"Получен токен сессии из cookie: {session_token[:20] if session_token else None}...")
    if not session_token:
        logger.debug(f"Cookie {settings.session_cookie_name} не найден. Все cookies: {list(request.cookies.keys())}")
        return None
    
    session_data = session_manager.verify_session(session_token)
    if session_data:
        logger.debug(f"Сессия успешно декодирована: domain={session_data.get('domain')}, yandex_id={session_data.get('yandex_id')}, login={session_data.get('login')}")
    else:
        logger.debug("Сессия не прошла проверку")
    return session_data


async def check_auth(request: Request) -> Optional[dict]:
    """Проверить авторизацию пользователя"""
    domain = get_domain_from_request(request)
    logger.debug(f"Проверка авторизации для домена: {domain}")
    logger.debug(f"Все cookies в запросе: {list(request.cookies.keys())}")
    session_data = get_session_from_cookie(request)
    
    if not session_data:
        logger.warning(f"Сессия не найдена для домена {domain}. Cookies: {list(request.cookies.keys())}")
        return None
    
    # Проверяем, что сессия для правильного домена
    session_domain = session_data.get("domain")
    if session_domain != domain:
        logger.debug(f"Сессия для другого домена: {session_domain} != {domain}")
        return None
    
    # Проверяем доступ пользователя к домену
    # Проверяем и по yandex_id и по login
    yandex_id = session_data.get("yandex_id", "")
    login = session_data.get("login", "")
    
    if not yandex_id and not login:
        logger.debug(f"yandex_id и login не найдены в сессии")
        return None
    
    # Проверяем доступ (поддерживаем и ID и login)
    is_allowed = db.is_user_allowed(domain, yandex_id) or (login and db.is_user_allowed(domain, login))
    if not is_allowed:
        user_identifier = login if login else yandex_id
        logger.debug(f"Пользователь {user_identifier} не имеет доступа к домену {domain}")
        logger.debug(f"Доступные пользователи для {domain}: {db.get_domain_users(domain)}")
        return None
    
    user_identifier = login if login else yandex_id
    logger.debug(f"Пользователь {user_identifier} авторизован для домена {domain}")
    return session_data


@app.get("/auth/login")
async def login(request: Request, error: Optional[str] = None):
    """Начало процесса авторизации"""
    domain = get_domain_from_request(request)
    
    # Если есть ошибка, логируем её
    if error:
        logger.warning(f"Ошибка авторизации для домена {domain}: {error}")
    
    # Кодируем домен в state для возврата после авторизации
    state = urllib.parse.quote(domain)
    
    authorize_url = yandex_oauth.get_authorize_url(state=state)
    logger.info(f"Редирект на авторизацию Yandex для домена {domain}: {authorize_url}")
    
    # Используем status_code=302 для явного редиректа
    response = RedirectResponse(url=authorize_url, status_code=302)
    return response


@app.get("/auth/callback")
async def callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Обработка callback от Yandex OAuth"""
    # Проверяем наличие ошибки от Yandex
    if error:
        logger.error(f"Ошибка от Yandex OAuth: {error}")
        domain = urllib.parse.unquote(state) if state else get_domain_from_request(request)
        error_url = f"https://{domain}/auth/login?error={urllib.parse.quote(error)}"
        return RedirectResponse(url=error_url, status_code=302)
    
    if not code:
        logger.error("Ошибка авторизации: отсутствует код")
        domain = get_domain_from_request(request)
        error_url = f"https://{domain}/auth/login?error=no_code"
        return RedirectResponse(url=error_url, status_code=302)
    
    # Получаем домен из state
    domain = urllib.parse.unquote(state) if state else get_domain_from_request(request)
    logger.info(f"Обработка callback для домена: {domain}")
    logger.debug(f"Cookies в запросе: {request.cookies}")
    
    # Получаем токен
    token_data = await yandex_oauth.get_token(code)
    if not token_data:
        logger.error(f"Ошибка получения токена для домена {domain}")
        error_url = f"https://{domain}/auth/login?error=token_error"
        return RedirectResponse(url=error_url, status_code=302)
    
    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(f"Токен не найден в ответе для домена {domain}")
        error_url = f"https://{domain}/auth/login?error=no_token"
        return RedirectResponse(url=error_url, status_code=302)
    
    # Получаем информацию о пользователе
    user_info = await yandex_oauth.get_user_info(access_token)
    if not user_info:
        logger.error(f"Не удалось получить информацию о пользователе для домена {domain}")
        error_url = f"https://{domain}/auth/login?error=user_info_error"
        return RedirectResponse(url=error_url, status_code=302)
    
    yandex_id = user_info.get("yandex_id", "")
    login = user_info.get("login", "")
    email = user_info.get("default_email", "")
    name = user_info.get("real_name") or user_info.get("display_name", "")
    
    # Логируем полученную информацию для отладки
    logger.info(f"Авторизация пользователя: yandex_id={yandex_id}, login={login}, email={email}, name={name}, domain={domain}")
    logger.info(f"Доступные пользователи для {domain}: {db.get_domain_users(domain)}")
    
    # Проверяем доступ пользователя к домену (по ID или по login)
    # Используем login если он указан в базе, иначе yandex_id
    user_identifier = login if login else yandex_id
    is_allowed = db.is_user_allowed(domain, yandex_id) or db.is_user_allowed(domain, login)
    logger.info(f"Проверка доступа: yandex_id={yandex_id}, login={login}, is_allowed={is_allowed}")
    
    if not is_allowed:
        logger.warning(f"Доступ запрещен: yandex_id={yandex_id}, login={login} не найден в списке пользователей домена {domain}")
        return HTMLResponse(
            f"<h1>Доступ запрещен</h1><p>У вас нет доступа к домену {domain}</p><p>Ваш Yandex ID: {yandex_id}</p><p>Ваш Login: {login}</p>",
            status_code=403
        )
    
    logger.info(f"Доступ разрешен, создаем сессию для yandex_id={yandex_id}, login={login}")
    
    # Сохраняем и yandex_id и login в сессию для проверки доступа
    # В сессию сохраняем yandex_id, но также проверяем доступ по login
    session_token = session_manager.create_session(yandex_id, email, name, domain, login=login)
    logger.info(f"Сессия создана, токен: {session_token[:50]}...")
    
    # Перенаправляем на исходный домен с установкой cookie
    redirect_url = f"https://{domain}/"
    response = RedirectResponse(url=redirect_url, status_code=302)
    
    # Устанавливаем cookie
    logger.info(f"Устанавливаем cookie {settings.session_cookie_name} для домена {domain}, redirect_url={redirect_url}")
    logger.debug(f"Параметры cookie: httponly={settings.session_cookie_httponly}, secure={settings.session_cookie_secure}, samesite={settings.session_cookie_samesite}")
    
    # Для поддоменов нужно установить domain, иначе cookie не будет работать
    # Устанавливаем domain как корневой домен без поддомена
    cookie_domain = None
    if domain and '.' in domain:
        # Извлекаем корневой домен (например, из bbspreads.aadolgov.com получаем .aadolgov.com)
        parts = domain.split('.')
        if len(parts) >= 2:
            cookie_domain = f".{'.'.join(parts[-2:])}"  # .aadolgov.com
            logger.debug(f"Устанавливаем cookie domain: {cookie_domain}")
    
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=settings.session_cookie_httponly,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_expire_hours * 3600,
        path="/",
        domain=cookie_domain  # Устанавливаем domain для работы на всех поддоменах
    )
    
    logger.info(f"Cookie установлен (domain={cookie_domain}), перенаправляем на {redirect_url}")
    logger.debug(f"Заголовки ответа: {dict(response.headers)}")
    return response


@app.get("/auth/logout")
async def logout(request: Request):
    """Выход из системы"""
    domain = get_domain_from_request(request)
    redirect_url = f"https://{domain}/"
    
    response = RedirectResponse(url=redirect_url)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/"
    )
    return response


@app.get("/auth/check")
async def check(request: Request):
    """Проверить статус авторизации (используется Nginx auth_request)"""
    session_data = await check_auth(request)
    
    if session_data:
        # Пользователь авторизован - возвращаем 200
        return JSONResponse({
            "authenticated": True,
            "user": {
                "yandex_id": session_data.get("yandex_id"),
                "email": session_data.get("email"),
                "name": session_data.get("name")
            }
        })
    else:
        # Пользователь не авторизован - возвращаем 401 для Nginx auth_request
        from fastapi import status
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"authenticated": False}
        )


@app.get("/auth/user")
async def get_user(request: Request):
    """Получить информацию о текущем пользователе"""
    session_data = await check_auth(request)
    
    if not session_data:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    return JSONResponse({
        "yandex_id": session_data.get("yandex_id"),
        "email": session_data.get("email"),
        "name": session_data.get("name"),
        "domain": session_data.get("domain")
    })


# API для управления пользователями (только для администратора)
@app.get("/api/admin/domains")
async def get_domains(request: Request):
    """Получить список всех доменов"""
    session_data = await check_auth(request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    # Проверка на администратора
    if session_data.get("yandex_id") != settings.admin_yandex_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    domains = db.get_all_domains()
    return JSONResponse(domains)


@app.get("/api/admin/domains/{domain}/users")
async def get_domain_users(domain: str, request: Request):
    """Получить список пользователей домена"""
    session_data = await check_auth(request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if session_data.get("yandex_id") != settings.admin_yandex_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    users = db.get_domain_users(domain)
    return JSONResponse({"domain": domain, "users": users})


@app.post("/api/admin/domains/{domain}/users/{yandex_id}")
async def add_user_to_domain(domain: str, yandex_id: str, request: Request):
    """Добавить пользователя к домену"""
    session_data = await check_auth(request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if session_data.get("yandex_id") != settings.admin_yandex_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    success = db.add_user_to_domain(domain, yandex_id)
    if success:
        return JSONResponse({"success": True, "message": f"Пользователь {yandex_id} добавлен к домену {domain}"})
    else:
        return JSONResponse({"success": False, "message": "Пользователь уже существует или ошибка"}), 400


@app.delete("/api/admin/domains/{domain}/users/{yandex_id}")
async def remove_user_from_domain(domain: str, yandex_id: str, request: Request):
    """Удалить пользователя из домена"""
    session_data = await check_auth(request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if session_data.get("yandex_id") != settings.admin_yandex_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    success = db.remove_user_from_domain(domain, yandex_id)
    if success:
        return JSONResponse({"success": True, "message": f"Пользователь {yandex_id} удален из домена {domain}"})
    else:
        return JSONResponse({"success": False, "message": "Пользователь не найден"}), 404


@app.post("/api/admin/domains/{domain}")
async def add_domain(domain: str, request: Request):
    """Добавить новый домен"""
    session_data = await check_auth(request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if session_data.get("yandex_id") != settings.admin_yandex_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    success = db.add_domain(domain)
    if success:
        return JSONResponse({"success": True, "message": f"Домен {domain} добавлен"})
    else:
        return JSONResponse({"success": False, "message": "Домен уже существует"}), 400


@app.get("/admin")
async def admin_panel(request: Request):
    """Админ-панель для управления пользователями"""
    session_data = await check_auth(request)
    if not session_data:
        return RedirectResponse(url="/auth/login")
    
    if session_data.get("yandex_id") != settings.admin_yandex_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Читаем HTML шаблон
    from pathlib import Path
    template_path = Path(__file__).parent / "templates" / "admin.html"
    
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    else:
        return HTMLResponse(
            "<h1>Админ-панель</h1><p>Используйте API для управления пользователями</p>",
            status_code=200
        )


@app.get("/health")
async def health():
    """Проверка здоровья сервиса"""
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.auth_server_host,
        port=settings.auth_server_port
    )

