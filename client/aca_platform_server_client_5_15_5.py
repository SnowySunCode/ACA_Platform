import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import math
import os
import sys
import html
import hashlib
import hmac
import uuid
import secrets
import time
import ssl
import copy
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    import certifi
except Exception:
    certifi = None


APP_TITLE = "ACA Platform"
APP_VERSION = "5.15.5"
APP_BUNDLE_ID = "com.apexcreatoracademy.acaplatform"
APP_ICON_RESOURCE = "aca_platform_icon.png"
DEFAULT_SERVER_URL = "https://capable-reverence-production-c65c.up.railway.app"


def _runtime_data_root():
    """Stable writable data directory for packaged builds; project cwd in script mode."""
    override = os.environ.get("ACA_PLATFORM_DATA_DIR")
    if override:
        root = os.path.abspath(os.path.expanduser(override))
    elif getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            root = os.path.expanduser("~/Library/Application Support/ACA Platform")
        elif os.name == "nt":
            root = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ACA Platform")
        else:
            root = os.path.expanduser("~/.local/share/ACA Platform")
    else:
        root = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(root, exist_ok=True)
    return root


def _persistent_user_state_root():
    """Stable per-user state directory for sessions/preferences."""
    override = os.environ.get("ACA_PLATFORM_STATE_DIR")
    if override:
        root = os.path.abspath(os.path.expanduser(override))
    elif sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support/ACA Platform")
    elif os.name == "nt":
        root = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ACA Platform")
    else:
        root = os.path.expanduser("~/.local/share/ACA Platform")
    os.makedirs(root, exist_ok=True)
    return root


def resource_path(name):
    """Resolve bundled resources under PyInstaller and normal source execution."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def apply_app_icon(window):
    """Apply the ACA Platform icon to Tk windows; keep a reference to avoid GC."""
    try:
        icon_path = resource_path(APP_ICON_RESOURCE)
        if os.path.exists(icon_path):
            icon = tk.PhotoImage(file=icon_path)
            window.iconphoto(True, icon)
            window._aca_platform_icon = icon
    except Exception:
        # The macOS .app bundle still uses the ICNS icon even if Tk iconphoto is unavailable.
        pass


APP_DATA_DIR = _runtime_data_root()
APP_STATE_DIR = _persistent_user_state_root()
DB_FILE = os.path.join(APP_DATA_DIR, "aca_system_db.json")
BACKUP_DIR = os.path.join(APP_DATA_DIR, "aca_backups")
SERVER_CONFIG_FILE = os.path.join(APP_DATA_DIR, "aca_server_config.json")
SESSION_FILE = os.path.join(APP_STATE_DIR, "aca_session.json")
CLIENT_PREFS_FILE = os.path.join(APP_STATE_DIR, "aca_client_prefs.json")
LEGACY_SESSION_FILE = os.path.join(APP_DATA_DIR, "aca_session.json")


def _env_truthy(name):
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def load_server_url():
    """Return the ACA server URL.

    Production builds always use the ACA Railway server unless a developer
    explicitly enables local mode with ACA_LOCAL_MODE=1.

    Priority:
      1) ACA_LOCAL_MODE=1 -> local/offline DataStore (developer only)
      2) ACA_SERVER_URL environment variable
      3) per-user/source aca_server_config.json
      4) built-in production Railway URL

    This prevents packaged builds from silently falling back to a local JSON
    database when a config file is missing.
    """
    if _env_truthy("ACA_LOCAL_MODE"):
        return None

    env = str(os.environ.get("ACA_SERVER_URL") or "").strip()
    if env:
        return env.rstrip("/")

    candidates = [SERVER_CONFIG_FILE]
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "aca_server_config.json"))
    except Exception:
        pass

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            value = str((cfg or {}).get("server_url") or "").strip()
            if value:
                return value.rstrip("/")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue

    return DEFAULT_SERVER_URL.rstrip("/")


WINDOW_W = 1200
WINDOW_H = 800

COLORS = {
    "bg": "#0b0b0d",
    "panel": "#141419",
    "panel2": "#1b1b22",
    "text": "#ffffff",
    "muted": "#8b8b98",
    "cyan": "#00e5ff",
    "green": "#00ff66",
    "pink": "#ff0066",
    "amber": "#ffb000",
    "grid": "#2b2b34",
    "hover": "#202833",
}

VALID_ASSESSMENT_WEIGHTS = (1, 2, 3, 4)
VALID_PHASES = tuple(range(1, 8))
INVITE_PREFIX = "ACA-TEACH-"
INVITE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# One-time built-in Principal Admin seed. The requested password and security
# answer are represented here only by PBKDF2-HMAC-SHA256 records; neither secret
# is written to the JSON database in plaintext. The seed is applied once and then
# permanently marked complete so subsequent user password changes are preserved.
SYSTEM_ADMIN_USERNAME = "admin"
SYSTEM_ADMIN_DISPLAY_NAME = "Principal Admin"
SYSTEM_ADMIN_SECURITY_QUESTION = "Название крутой"
SYSTEM_ADMIN_PASSWORD_HASH = {
    "salt": "ca215e6bd398c06ed63fa2bd4e1614a6",
    "digest": "ba9d0a58f68cce883fd96b3d45386815438b191f10c53855877a3794262d3f91",
    "iterations": 310000,
    "algorithm": "pbkdf2_hmac_sha256",
}
SYSTEM_ADMIN_SECURITY_ANSWER_HASH = {
    "salt": "a176525b96042cbcb9c70c99dab97dcc",
    "digest": "5ebe41c71b8ded49a9b07627daa44564360d22963ec1ad265be10345b7e8136e",
    "iterations": 310000,
    "algorithm": "pbkdf2_hmac_sha256",
}


# --- Russian localization -----------------------------------------------------
# Internal role/status identifiers remain English for database compatibility;
# only presentation strings are translated.
UI_LANGUAGE = "ru"

RU_TEXT = {
    "Sign in": "Войти", "Create account": "Регистрация", "Welcome back": "С возвращением",
    "Language": "Язык", "Language changed": "Язык изменён",
    "Created": "Создан", "Last login": "Последний вход", "Never": "Никогда",
    "Sign in to continue to your academy workspace.": "Войдите, чтобы продолжить работу в академии.",
    "Forgot password?": "Забыли пароль?", "Recover password": "Восстановление пароля",
    "Recovery code": "Контрольный код", "Security question": "Контрольный вопрос",
    "Use your private recovery code or the security question configured for your account.": "Используйте личный контрольный код или настроенный контрольный вопрос.",
    "Load question": "Показать вопрос", "Back": "Назад", "Reset password": "Сбросить пароль",
    "Create an account": "Создать аккаунт", "Student": "Ученик", "Teacher": "Учитель",
    "STUDENT": "УЧЕНИК", "TEACHER": "УЧИТЕЛЬ", "ADMIN": "АДМИН", "USER": "ПОЛЬЗОВАТЕЛЬ",
    "PRINCIPAL ADMIN": "ГЛАВНЫЙ АДМИН", "Principal Admin": "Главный администратор",
    "Private profile, GPA, lessons and submissions": "Личный профиль, GPA, уроки и работы",
    "Invite-only access with phase-level grading rights": "Доступ по приглашению с правами на выбранные фазы",
    "Full academy control, accounts, access and backups": "Полный контроль академии, аккаунтов, доступа и резервных копий",
    "Secure academy workspace for students, instructors,\nand principal administration.": "Защищённая рабочая среда академии для учеников,\nпреподавателей и администратора.",
    "Student registration is open. Teacher registration requires a one-time invite code.": "Регистрация ученика открыта. Для регистрации учителя нужен одноразовый invite-код.",
    "DISPLAY NAME": "ОТОБРАЖАЕМОЕ ИМЯ", "USERNAME": "ЛОГИН", "PASSWORD": "ПАРОЛЬ",
    "CONFIRM PASSWORD": "ПОВТОРИТЕ ПАРОЛЬ", "NEW PASSWORD": "НОВЫЙ ПАРОЛЬ",
    "CONFIRM NEW PASSWORD": "ПОВТОРИТЕ НОВЫЙ ПАРОЛЬ", "CURRENT PASSWORD": "ТЕКУЩИЙ ПАРОЛЬ",
    "AGE": "ВОЗРАСТ", "TEACHER INVITE CODE": "INVITE-КОД УЧИТЕЛЯ", "ANSWER": "ОТВЕТ",
    "RECOVERY CODE": "КОНТРОЛЬНЫЙ КОД", "SECURITY QUESTION": "КОНТРОЛЬНЫЙ ВОПРОС",
    "Name shown inside ACA Platform": "Имя, которое будет показано в ACA Platform",
    "At least 8 characters": "Не менее 8 символов", "Repeat password": "Повторите пароль",
    "Repeat new password": "Повторите новый пароль", "Security answer": "Ответ на контрольный вопрос",
    "Enter username, then load the question.": "Введите логин и нажмите «Показать вопрос».",
    "Security question is unavailable for this account.": "Для этого аккаунта контрольный вопрос не настроен.",
    "INSTALLATION OWNER": "ВЛАДЕЛЕЦ СИСТЕМЫ", "Principal setup": "Настройка администратора",
    "Principal Admin is created separately and only once. Normal registration never grants administrator rights.": "Главный администратор создаётся отдельно и только один раз. Обычная регистрация никогда не выдаёт права администратора.",
    "One-time installation owner account. This path is separate from Student and Teacher registration.": "Однократное создание аккаунта владельца системы. Этот сценарий отделён от регистрации ученика и учителя.",
    "ADMIN ACCESS": "ДОСТУП АДМИНИСТРАТОРА",
    "Creates the only self-bootstrapped Principal Admin. Type PRINCIPAL below to confirm.": "Создаёт единственного начального главного администратора. Для подтверждения введите PRINCIPAL.",
    "Create Principal Admin": "Создать главного администратора", "Principal name": "Имя администратора",
    "SETUP CONFIRMATION": "ПОДТВЕРЖДЕНИЕ", "Type PRINCIPAL": "Введите PRINCIPAL",
    "Password reset required": "Требуется смена пароля",
    "An administrator reset this account password. Choose a new private password before entering ACA Platform.": "Администратор сбросил пароль этого аккаунта. Перед входом задайте новый личный пароль.",
    "Save new password": "Сохранить новый пароль", "Your recovery code": "Ваш контрольный код",
    "New recovery code": "Новый контрольный код", "Principal recovery code": "Контрольный код администратора",
    "Password recovered": "Пароль восстановлен", "Password changed": "Пароль изменён",
    "Password updated securely.": "Пароль безопасно обновлён.",
    "Overview": "Обзор", "Journal": "Журнал", "Electronic Journal": "Электронный журнал",
    "Analytics": "Аналитика", "Quantum Analytics": "Аналитика", "Graduation": "Выпуск",
    "Graduation Control": "Выпускной контроль", "Access & Accounts": "Доступ и аккаунты",
    "Access & Teachers": "Доступ и учителя", "Security": "Безопасность", "Log out": "Выйти",
    "WORKSPACE": "РАБОЧАЯ ОБЛАСТЬ", "Control plane  •  v": "Панель управления  •  v",
    "No student": "Ученик не выбран", "Create a profile": "Создайте профиль",
    "Backup database": "Резервная копия базы", "＋ Student": "＋ Ученик",
    "Refresh students": "Обновить учеников", "Last sync —": "Последнее обновление —",
    "Grade ledger": "Журнал оценок",
    "120 lessons • frozen lesson directory • unlimited assessment history": "120 уроков • закреплённая колонка уроков • неограниченная история оценок",
    "All": "Все", "Graded": "С оценками", "Active": "Активный", "Empty": "Пустые", "At risk": "Риск",
    "Compact": "Компактно", "Comfort": "Удобно", "Spacious": "Просторно",
    "Fit": "Вписать", "Reset": "Сброс", "Go": "Перейти", "ZOOM": "МАСШТАБ", "DENSITY": "ПЛОТНОСТЬ",
    "Search ID, lesson, module, phase…": "Поиск по ID, уроку, модулю, фазе…",
    "Lesson inspector": "Инспектор урока", "Select a lesson": "Выберите урок",
    "Select a row or grade cell. Double-click a grade to edit; double-click a lesson to append.": "Выберите строку или оценку. Двойной клик по оценке — редактирование, по уроку — добавить оценку.",
    "GEOMETRY DASH LEVEL ID": "ID УРОВНЯ GEOMETRY DASH", "SHOWCASE URL": "ССЫЛКА НА SHOWCASE",
    "Save Level ID": "Сохранить Level ID", "Save showcase": "Сохранить showcase",
    "No grades yet. Double-click the first empty grade cell to add one.": "Оценок пока нет. Дважды щёлкните по первой пустой ячейке, чтобы добавить оценку.",
    "Phase performance": "Результаты по фазам", "Current weighted average by training block": "Текущий средневзвешенный результат по учебным блокам",
    "Legacy import": "Импорт старых данных", "Open journal": "Открыть журнал",
    "Weighted GPA": "Средневзвешенный GPA", "Grade transactions": "Оценок", "Lessons touched": "Уроков с оценками",
    "Consistency": "Стабильность", "GPA trajectory": "Динамика GPA", "Clutch GPA simulator": "Симулятор целевого GPA",
    "Target GPA": "Целевой GPA", "Run simulation": "Рассчитать", "Projection": "Прогноз",
    "Strategic output": "Стратегический расчёт", "Current GPA": "Текущий GPA", "10/10 needed": "Нужно оценок 10/10",
    "Graduation dossier": "Выпускное досье", "Grand 100-point Solo-Level Exam": "Итоговый 100-балльный сольный экзамен",
    "Exam score": "Баллы экзамена", "Save exam score": "Сохранить баллы", "Moderator send requests": "Запросы модераторам",
    "Gameplay moderator request": "Запрос gameplay-модератору", "Art review request": "Запрос арт-проверки",
    "Verification request": "Запрос верификации", "Export graduation report": "Экспортировать выпускной отчёт",
    "Generate a polished HTML performance report with GPA, phase analytics and grade ledger.": "Создать HTML-отчёт с GPA, аналитикой по фазам и журналом оценок.",
    "Teacher onboarding": "Регистрация учителей", "Generate one-time invite codes with explicit phase-level edit permissions.": "Создавайте одноразовые invite-коды с правами редактирования по выбранным фазам.",
    "TEACHER LABEL": "ИМЯ / МЕТКА УЧИТЕЛЯ", "AUTHORIZED PHASES": "РАЗРЕШЁННЫЕ ФАЗЫ",
    "Generate invite code": "Создать invite-код", "Invites & account registry": "Invite-коды и аккаунты",
    "TEACHER INVITES": "INVITE-КОДЫ УЧИТЕЛЕЙ", "REGISTERED ACCOUNTS": "ЗАРЕГИСТРИРОВАННЫЕ АККАУНТЫ",
    "No invite codes yet": "Invite-кодов пока нет", "Disable": "Отключить", "Enable": "Включить", "Reissue": "Перевыпустить",
    "Role": "Роль", "Change role": "Сменить роль", "Force password reset": "Принудительно сбросить пароль",
    "Account security": "Безопасность аккаунта", "Change password": "Сменить пароль",
    "Replace recovery code": "Перевыпустить контрольный код",
    "If you lose the current recovery code, enter your current password above and issue a replacement. The old code becomes invalid immediately.": "Если текущий контрольный код потерян, введите пароль выше и выпустите новый. Старый код сразу станет недействительным.",
    "Ready": "Готово", "ONLINE": "ОНЛАЙН", "SYNCING": "СИНХРОНИЗАЦИЯ", "DELAYED": "ЗАДЕРЖКА", "ERROR": "ОШИБКА",
    "FROZEN LESSON DIRECTORY": "ЗАКРЕПЛЁННЫЕ УРОКИ", "PHASE / ID": "ФАЗА / ID", "LESSON / MODULE": "УРОК / МОДУЛЬ",
    "AVG": "СРЕД.", "BASE": "ВЕС", "ASSESSMENT HISTORY  •  HORIZONTAL SCROLL": "ИСТОРИЯ ОЦЕНОК  •  ГОРИЗОНТАЛЬНАЯ ПРОКРУТКА",
    "Select or create a student": "Выберите или создайте ученика", "No grade history yet": "Истории оценок пока нет",
    "Run the clutch simulator to draw the projection": "Запустите симулятор, чтобы построить прогноз",
    "Create your first student profile": "Создайте первый профиль ученика",
    "The dashboard will populate with GPA, progress and phase analytics.": "Здесь появятся GPA, прогресс и аналитика по фазам.",
    "STUDENT COMMAND CENTER": "ПАНЕЛЬ УЧЕНИКА", "WEIGHTED GPA": "СРЕДНЕВЗВЕШЕННЫЙ GPA",
    "Curriculum complete": "Программа завершена", "COMPLETE": "ЗАВЕРШЕНО",
    "No active student selected.": "Активный ученик не выбран.", "No students": "Нет учеников",
    "Create student profile": "Создать профиль ученика", "New student": "Новый ученик", "Student name": "Имя ученика",
    "SKILL CLASS": "УРОВЕНЬ", "ACTIVE TRACKS": "НАПРАВЛЕНИЯ", "Gameplay, Decoration": "Gameplay, Decoration",
    "Save transaction": "Сохранить оценку", "Grade transaction": "Оценка", "GRADE": "ОЦЕНКА",
    "ASSESSMENT WEIGHT": "ВЕС ОЦЕНКИ", "ASSESSMENT TYPE": "ТИП ОЦЕНКИ", "Homework skipped / delinquent": "Домашняя работа пропущена / просрочена",
    "Delete grade": "Удалить оценку", "Delete this grade transaction?": "Удалить эту оценку?",
    "Level ID saved": "Level ID сохранён", "Showcase URL saved": "Showcase URL сохранён",
    "Account enabled": "Аккаунт включён", "Account disabled": "Аккаунт отключён", "Account role updated": "Роль аккаунта обновлена",
    "Invite enabled": "Invite-код включён", "Invite disabled": "Invite-код отключён", "Teacher invite generated": "Invite-код учителя создан",
    "Manual refresh failed": "Ручное обновление не удалось", "Backup": "Резервная копия", "Access denied": "Доступ запрещён",
    "Account": "Аккаунт", "Teacher invite": "Invite-код учителя", "Lesson not found": "Урок не найден",
    "PENDING": "ОЖИДАЕТ", "USED": "ИСПОЛЬЗОВАН", "DISABLED": "ОТКЛЮЧЁН", "ACTIVE": "АКТИВЕН",
    "1:20+ long-form graduation layout": "Выпускной уровень длительностью 1:20+",
    "A new profile starts with an empty 120-lesson ledger.": "Новый профиль создаётся с пустым журналом на 120 уроков.",
    "ACA / MASTER GRADE SHEET": "ACA / ГЛАВНЫЙ ЖУРНАЛ",
    "Administrator access required": "Требуется доступ администратора",
    "Apply role": "Применить роль", "BASELINE GPA": "ИСХОДНЫЙ GPA",
    "Calculate exact flawless-score vector across remaining lessons": "Рассчитать точное количество идеальных оценок по оставшимся урокам",
    "Create profile": "Создать профиль", "Current session": "Текущая сессия",
    "Deco Instructor": "Преподаватель декора", "Delete": "Удалить", "Generate": "Сгенерировать",
    "H 00%  •  100%": "Г 00%  •  100%", "HISTORICAL LESSON COUNT": "КОЛИЧЕСТВО УРОКОВ В ИСТОРИИ",
    "Legacy GPA backfill": "Восстановление старого GPA",
    "Reconstruct historical grades to match a precise baseline.": "Восстановить исторические оценки так, чтобы точно совпал исходный GPA.",
    "Recovery code replaced. Old code invalidated.": "Контрольный код заменён. Старый код недействителен.",
    "Run exact backfill": "Выполнить точное восстановление", "SCORE / 10": "ОЦЕНКА / 10",
    "TEACHER PHASE ACCESS": "ДОСТУП УЧИТЕЛЯ К ФАЗАМ", "Temporary password": "Временный пароль",
    "The user will be forced to choose a new private password at the next sign-in.": "При следующем входе пользователь будет обязан установить новый личный пароль.",
    "Weighted after every recorded grade": "Пересчитывается после каждой оценки",
    "⇧ wheel: horizontal  •  Ctrl/Cmd + wheel: zoom  •  arrows: navigate  •  Enter: edit": "⇧ колесо: горизонтально  •  Ctrl/Cmd + колесо: масштаб  •  стрелки: навигация  •  Enter: редактировать",
    "Base Gameplay & Geometry": "Базовый геймплей и геометрия",
    "Advanced Mechanics & Speed Dynamics": "Продвинутая механика и динамика скорости",
    "Higher League Outline Structures": "Продвинутые структуры и контуры",
    "Mega-Mechanics 2.2 & Duals": "Мега-механики 2.2 и дуалы",
    "Logic, Coding & Trigger Wizardry": "Логика, кодинг и триггеры",
    "Low-Extreme Hardcore & Asymmetrical Duals": "Low-Extreme Hardcore и асимметричные дуалы",
    "Art & Decoration Academy": "Академия арта и декора",
    "Lesson": "Урок", "Exam": "Экзамен",
    "Class participation / live quizzes": "Работа на занятии / живые квизы",
    "Homework layouts": "Домашние layout-задания",
    "Advanced milestones": "Продвинутые контрольные этапы",
    "Final Graduation Exam": "Итоговый выпускной экзамен",
    "Invalid username or password.": "Неверный логин или пароль.",
    "This username is already registered.": "Этот логин уже зарегистрирован.",
    "Username must contain 3–32 characters.": "Логин должен содержать от 3 до 32 символов.",
    "Username may contain letters, numbers, dot, underscore, and hyphen only.": "В логине можно использовать только буквы, цифры, точку, подчёркивание и дефис.",
    "Password must contain at least 8 characters.": "Пароль должен содержать не менее 8 символов.",
    "Password is too long.": "Пароль слишком длинный.",
    "Passwords do not match.": "Пароли не совпадают.",
    "Current password is incorrect.": "Текущий пароль указан неверно.",
    "Temporary password is incorrect.": "Временный пароль указан неверно.",
    "New password must be different from the current password.": "Новый пароль должен отличаться от текущего.",
    "Display name is required.": "Укажите отображаемое имя.",
    "Age must be a whole number.": "Возраст должен быть целым числом.",
    "Invite code is invalid.": "Invite-код недействителен.",
    "Invite code has already been used.": "Этот invite-код уже использован.",
    "Invite code has been disabled by an administrator.": "Invite-код отключён администратором.",
    "Invite code not found.": "Invite-код не найден.",
    "Account not found.": "Аккаунт не найден.",
    "Account not found or disabled.": "Аккаунт не найден или отключён.",
    "Only an administrator can perform this operation.": "Эта операция доступна только администратору.",
    "The last active administrator cannot be demoted.": "Нельзя понизить роль последнего активного администратора.",
    "The last active administrator cannot be disabled.": "Нельзя отключить последнего активного администратора.",
    "You cannot disable the administrator account currently in use.": "Нельзя отключить аккаунт администратора, под которым выполнен текущий вход.",
    "Change your own administrator role from another administrator account.": "Смените роль этого администратора из другого администраторского аккаунта.",
    "Role must be ADMIN, TEACHER, or STUDENT.": "Роль должна быть ADMIN, TEACHER или STUDENT.",
    "Recovery code must contain 8 code characters.": "Контрольный код должен содержать 8 символов кода.",
    "Recovery failed. Check the username and recovery code, or try again later.": "Восстановление не удалось. Проверьте логин и контрольный код или попробуйте позже.",
    "Recovery failed. Check the username and security answer, or try again later.": "Восстановление не удалось. Проверьте логин и ответ на контрольный вопрос или попробуйте позже.",
    "Security answer is invalid.": "Ответ на контрольный вопрос неверный.",
    "This account does not require a forced password change.": "Для этого аккаунта принудительная смена пароля не требуется.",
    "Administrator accounts can only be created through Principal Setup.": "Аккаунт администратора можно создать только через отдельную настройку Principal Admin.",
    "Administrator registration is already closed for this installation.": "Первичная регистрация администратора для этой установки уже закрыта.",
    "Principal Admin already exists.": "Главный администратор уже существует.",
    "Type PRINCIPAL in the setup confirmation field.": "Введите PRINCIPAL в поле подтверждения.",
}


# Final presentation-layer translations not represented by backend identifiers.
RU_TEXT.update({
    "Change account role": "Смена роли аккаунта",
    "Force password reset": "Принудительный сброс пароля",
    "NAME": "ИМЯ",
    "Unranked": "Без ранга",
    "default": "по умолчанию",
    "eff": "итог",
    "HW skip": "пропуск ДЗ",
    "GRADE": "ОЦЕНКА",
    "Completion": "Прогресс",
    "Grades": "Оценки",
    "Solo exam": "Сольный экзамен",
    "Module": "Модуль",
    "HTML report": "HTML-отчёт",
    "ACA Graduation Report": "Выпускной отчёт ACA",
    "Change account role": "Смена роли аккаунта",
    "Required for security changes": "Требуется для изменений безопасности",
    "Recovery code replaced": "Контрольный код заменён",
    "Save this new recovery code:": "Сохраните новый контрольный код:",
    "The previous recovery code is now invalid.": "Предыдущий контрольный код теперь недействителен.",
    "It has been copied to the clipboard.": "Код скопирован в буфер обмена.",
    "Temporary password reset; copied to clipboard": "Временный пароль сброшен и скопирован в буфер обмена",
    "Password updated securely.": "Пароль безопасно обновлён.",
    "Recovery code replaced. Old code invalidated.": "Контрольный код заменён. Старый код недействителен.",
    "Advanced milestones / complex duals / triggers": "Продвинутые этапы / сложные дуалы / триггеры",
    "Gameplay": "Геймплей",
    "Decoration": "Декор",
    "Curriculum completion": "Завершение программы",
    "TARGET": "ЦЕЛЬ",
    "PINNED": "ЗАКРЕПЛЕНО",
    "NEW_PROFILE": "НОВЫЙ ПРОФИЛЬ",
    "PROBATION_LOCKED": "ИСПЫТАТЕЛЬНЫЙ РЕЖИМ",
    "TEAM_APPROVED": "ДОПУЩЕН В КОМАНДУ",
    "ACTIVE_CORE": "АКТИВНЫЙ СОСТАВ",
})

# Curriculum names are localized separately from stored canonical English values.
LESSON_RU = {
    "Balance": "Баланс",
    "Solid Structuring": "Построение цельных структур",
    "Ship Physics": "Физика корабля",
    "Musical Sync": "Музыкальная синхронизация",
    "Slopes": "Склоны",
    "Ball / Robot": "Шар / робот",
    "UFO Control": "Управление UFO",
    "Wave Basics": "Основы волны",
    "Alpha Readability": "Читаемость через альфа-канал",
    "Gravity Portals": "Порталы гравитации",
    "Speed Changes": "Смена скорости",
    "Orbs on Ship / Wave": "Орбы на корабле / волне",
    "Upside-Down": "Перевёрнутый геймплей",
    "Teleports": "Телепорты",
    "Mechanics Integration Review": "Проверка интеграции механик",
    "Outline Weights": "Толщина контуров",
    "Air Contours": "Воздушные контуры",
    "Jitter / Click Variety": "Джиттер / разнообразие кликов",
    "Layout Readability": "Читаемость layout",
    "Timings / Fakes": "Тайминги / фейки",
    "Sightread Test": "Тест на читаемость с первого взгляда",
    "Cherry Team Workflow": "Рабочий процесс Cherry Team",
    "Hitbox Stress Test": "Стресс-тест хитбоксов",
    "Spider Teleport": "Телепорт паука",
    "Swingcopter": "Свингкоптер",
    "2.2 Triggers": "Триггеры 2.2",
    "Symmetrical Duals": "Симметричные дуалы",
    "Mirror Duals": "Зеркальные дуалы",
    "Layout Stitching": "Сшивка layout",
    "Gameplay Exam": "Экзамен по геймплею",
    "Move Trigger Fundamentals": "Основы Move Trigger",
    "Rotate Trigger Fundamentals": "Основы Rotate Trigger",
    "Follow Trigger": "Follow Trigger",
    "Lock Systems": "Системы Lock",
    "Camera Zoom": "Масштаб камеры",
    "Camera Rotate": "Поворот камеры",
    "Camera Edge": "Границы камеры",
    "Spawn Trigger": "Spawn Trigger",
    "Toggle Networks": "Сети Toggle",
    "Touch Trigger": "Touch Trigger",
    "Count Trigger": "Count Trigger",
    "Item IDs": "ID предметов",
    "Pickup / Persistent Counters": "Pickup / постоянные счётчики",
    "If / Else Conditional Logic": "Условная логика If / Else",
    "Multi-Condition Logic": "Логика с несколькими условиями",
    "State Machines": "Конечные автоматы",
    "Bossfight Motion Logic": "Логика движения босса",
    "Bossfight Damage Logic": "Логика урона босса",
    "Bossfight Phase Logic": "Логика фаз босса",
    "Shader & Visual Trigger Integration": "Интеграция шейдеров и визуальных триггеров",
    "Event Trigger Chains": "Цепочки Event Trigger",
    "Optimization of Trigger Groups": "Оптимизация групп триггеров",
    "Debugging Trigger Race Conditions": "Отладка гонок триггеров",
    "Custom Bossfight": "Кастомный боссфайт",
    "Trigger Exam": "Экзамен по триггерам",
    "Extreme Balance": "Баланс Extreme",
    "Fast Switches": "Быстрые переключения",
    "Dual Hitboxes": "Хитбоксы в дуалах",
    "Cube + Ball Dual": "Дуал куб + шар",
    "Ship + Robot Dual": "Дуал корабль + робот",
    "Fast-Click Drops": "Дропы с быстрыми кликами",
    "60Hz Bug Fixing": "Исправление багов на 60 Гц",
    "144Hz Bug Fixing": "Исправление багов на 144 Гц",
    "240Hz Bug Fixing": "Исправление багов на 240 Гц",
    "Extreme Verification": "Верификация Extreme",
    "Color Theory I": "Теория цвета I",
    "Color Theory II": "Теория цвета II",
    "Palette Hierarchy": "Иерархия палитры",
    "Blending Modes": "Режимы смешивания",
    "Gradient Control": "Управление градиентами",
    "Pulse Sync Basics": "Основы синхронизации Pulse",
    "Pulse Sync Advanced": "Продвинутая синхронизация Pulse",
    "Beat-Driven Color Automation": "Автоматизация цвета по биту",
    "Glow Fundamentals": "Основы свечения",
    "Glow Layering": "Слои свечения",
    "Shading Fundamentals": "Основы шейдинга",
    "Directional Lighting": "Направленное освещение",
    "Ambient Occlusion Illusion": "Имитация ambient occlusion",
    "Air Deco Basics": "Основы воздушного декора",
    "Air Deco Density": "Плотность воздушного декора",
    "Negative Space Control": "Работа с негативным пространством",
    "Block Design I": "Дизайн блоков I",
    "Block Design II": "Дизайн блоков II",
    "Block Design III": "Дизайн блоков III",
    "Material Language": "Язык материалов",
    "Texture Rhythm": "Ритм текстур",
    "Edge Detailing": "Детализация краёв",
    "Foreground Framing": "Композиция переднего плана",
    "Background Composition": "Композиция фона",
    "Custom Backgrounds": "Кастомные фоны",
    "Parallax I": "Параллакс I",
    "Parallax II": "Параллакс II",
    "Depth Separation": "Разделение по глубине",
    "Particle Language": "Язык частиц",
    "Atmospheric FX": "Атмосферные эффекты",
    "Fog & Bloom Simulation": "Имитация тумана и bloom",
    "Motion Decoration": "Декор в движении",
    "Decorative Trigger Choreography": "Хореография декоративных триггеров",
    "Color Channel Systems": "Системы цветовых каналов",
    "Object Group Architecture": "Архитектура групп объектов",
    "Theme Consistency Review": "Проверка целостности темы",
    "Readability Under Decoration": "Читаемость при декорировании",
    "Gameplay / Deco Alignment": "Согласование геймплея и декора",
    "LDM Planning": "Планирование LDM",
    "LDM Optimization": "Оптимизация LDM",
    "Object Count Optimization": "Оптимизация количества объектов",
    "Draw-Call Awareness": "Контроль draw calls",
    "Performance Audit": "Аудит производительности",
    "Transition Polish": "Полировка переходов",
    "Section Stitching": "Сшивка секций",
    "Megacollab Handoff Standards": "Стандарты передачи работы в мегаколлабе",
    "Megacollab Style Matching": "Согласование стиля мегаколлаба",
    "Megacollab Polish I": "Полировка мегаколлаба I",
    "Megacollab Polish II": "Полировка мегаколлаба II",
    "Final Art Direction": "Финальная арт-дирекция",
    "Presentation Capture": "Запись презентационного материала",
    "Portfolio Packaging": "Оформление портфолио",
    "Moderator Readiness": "Готовность к модерации",
    "Phase 7 Master Review": "Итоговая проверка фазы 7",
    "Art & Decoration Graduation Exam": "Выпускной экзамен по арту и декору",
}

EN_TOOLTIPS = {
    "language_switch": "Switch the interface language. Your choice is saved and restored on the next launch.",
    "language_badge": "Current interface language.",
    "student_selector": "Choose the student whose dashboard, journal and analytics are shown in this window.",
    "refresh_students": "Force a full reload of the shared database and refresh the student list if live-sync missed an update.",
    "live_sync": "Live-sync watches ACA Server for changes from other ACA Platform clients. Green means online, yellow means syncing or delayed, red means an error.",
    "add_student": "Create a new student profile with an empty 120-lesson journal.",
    "security": "Change your password or replace your recovery code.",
    "logout": "End the current session and return to the sign-in screen.",
    "backup": "Create a timestamped backup copy of the academy database.",
    "nav_overview": "Open the student overview and phase performance dashboard.",
    "nav_journal": "Open the 120-lesson grade journal.",
    "nav_analytics": "Open GPA analytics and the target-GPA simulator.",
    "nav_graduation": "Open graduation controls, moderator requests and report export.",
    "nav_access": "Manage teacher invites, accounts, roles and forced password resets.",
    "journal_phase": "Filter the journal by curriculum phase.",
    "journal_search": "Search by lesson ID, lesson name, module or phase. Russian lesson names are searchable in RU mode.",
    "journal_status": "Filter lessons by grading state: graded, active, empty or at risk.",
    "journal_jump": "Enter a lesson ID such as L42 and jump directly to it.",
    "journal_active": "Jump to the student's current active lesson.",
    "journal_density": "Change row density without changing stored data.",
    "journal_zoom": "Scale the journal between 75% and 150%.",
    "journal_fit": "Set a compact zoom that keeps the grade sheet readable.",
    "journal_reset": "Reset phase, status, search, density, zoom and horizontal position.",
    "journal_scroll_left": "Scroll the assessment history one step to the left.",
    "journal_scroll_right": "Scroll the assessment history one step to the right.",
    "level_id": "Geometry Dash level ID: 8 or 9 digits. Saving it does not change grades.",
    "showcase_url": "Attach a YouTube, Shorts or TikTok showcase URL to this lesson.",
    "login_language": "Choose the language used on the sign-in, registration and recovery screens.",
    "auth_mode": "Switch between sign in and account registration.",
    "forgot_password": "Recover access using a one-time recovery code or your security question.",
    "recovery_method": "Choose how to verify account ownership for password recovery.",
    "role_selector": "Choose the account role. Teacher access can then be limited to selected phases.",
    "temporary_password": "Generate or enter a temporary password. The user will be forced to replace it at the next sign-in.",
    "recovery_replace": "Issue a new recovery code. The previous code becomes invalid immediately.",
}

RU_TOOLTIPS = {
    "language_switch": "Переключает язык интерфейса. Выбор сохраняется и восстанавливается при следующем запуске.",
    "language_badge": "Текущий язык интерфейса.",
    "student_selector": "Выберите ученика, чьи обзор, журнал и аналитика показаны в этом окне.",
    "refresh_students": "Принудительно перечитать общую базу и обновить список учеников, если live-sync пропустил изменение.",
    "live_sync": "Live-sync следит за изменениями на ACA Server от других клиентов ACA Platform. Зелёный — онлайн, жёлтый — синхронизация или задержка, красный — ошибка.",
    "add_student": "Создать новый профиль ученика с пустым журналом на 120 уроков.",
    "security": "Сменить пароль или перевыпустить контрольный код восстановления.",
    "logout": "Завершить текущую сессию и вернуться на экран входа.",
    "backup": "Создать резервную копию базы академии с отметкой времени.",
    "nav_overview": "Открыть обзор ученика и результаты по учебным фазам.",
    "nav_journal": "Открыть журнал оценок на 120 уроков.",
    "nav_analytics": "Открыть аналитику GPA и симулятор целевого GPA.",
    "nav_graduation": "Открыть выпускной контроль, запросы модераторам и экспорт отчёта.",
    "nav_access": "Управлять invite-кодами учителей, аккаунтами, ролями и принудительным сбросом пароля.",
    "journal_phase": "Фильтр журнала по учебной фазе.",
    "journal_search": "Поиск по ID, названию урока, модулю или фазе. В режиме RU можно искать по русским названиям уроков.",
    "journal_status": "Фильтр уроков по состоянию: с оценками, активный, пустые или группа риска.",
    "journal_jump": "Введите ID урока, например L42, чтобы сразу перейти к нему.",
    "journal_active": "Перейти к текущему активному уроку ученика.",
    "journal_density": "Изменить плотность строк без изменения сохранённых данных.",
    "journal_zoom": "Масштабировать журнал от 75% до 150%.",
    "journal_fit": "Установить компактный масштаб, сохранив читаемость журнала.",
    "journal_reset": "Сбросить фазу, статус, поиск, плотность, масштаб и горизонтальную прокрутку.",
    "journal_scroll_left": "Прокрутить историю оценок на один шаг влево.",
    "journal_scroll_right": "Прокрутить историю оценок на один шаг вправо.",
    "level_id": "ID уровня Geometry Dash: 8 или 9 цифр. Сохранение ID не меняет оценки.",
    "showcase_url": "Привязать к уроку ссылку на showcase в YouTube, Shorts или TikTok.",
    "login_language": "Выберите язык экрана входа, регистрации и восстановления доступа.",
    "auth_mode": "Переключение между входом и регистрацией аккаунта.",
    "forgot_password": "Восстановить доступ с помощью одноразового контрольного кода или контрольного вопроса.",
    "recovery_method": "Выберите способ подтверждения владельца аккаунта для восстановления пароля.",
    "role_selector": "Выберите роль аккаунта. Для учителя затем можно ограничить доступ выбранными фазами.",
    "temporary_password": "Сгенерируйте или задайте временный пароль. При следующем входе пользователь будет обязан его заменить.",
    "recovery_replace": "Выпустить новый контрольный код. Предыдущий код сразу станет недействительным.",
}

RU_SUBSTRINGS = [
    ("Secure academy workspace for students, instructors,\nand principal administration.", "Защищённая рабочая среда академии для учеников,\nпреподавателей и администратора."),
    ("Last sync ", "Последнее обновление "),
    ("Students refreshed • ", "Ученики обновлены • "),
    (" loaded", " загружено"),
    ("Live sync • database updated", "Live-sync • база обновлена"),
    ("Journal zoom ", "Масштаб журнала "),
    ("Journal density: ", "Плотность журнала: "),
    ("Journal view reset", "Вид журнала сброшен"),
    ("Jumped to ", "Переход к "),
    ("Phase ", "Фаза "),
    ("Base phase weight ", "Базовый вес фазы "),
    ("default assessment", "вес оценки по умолчанию"),
    ("No grades yet", "Оценок пока нет"),
    ("Homework skips", "Пропуски ДЗ"),
    ("Active lesson", "Активный урок"),
    ("Curriculum", "Программа"),
    ("Grade records", "Записей оценок"),
    ("Weighted GPA", "Средневзвешенный GPA"),
    ("Required consecutive flawless scores: ", "Требуется подряд оценок 10/10: "),
    ("Current weighted GPA: ", "Текущий средневзвешенный GPA: "),
    ("Projected GPA at crossing: ", "GPA при достижении цели: "),
    ("Maximum projected GPA: ", "Максимальный прогноз GPA: "),
    ("Target: ", "Цель: "),
    ("Report exported: ", "Отчёт экспортирован: "),
    ("Backup created: ", "Резервная копия создана: "),
    ("Teacher invite generated", "Invite-код учителя создан"),
    ("Invite reissued: ", "Invite-код перевыпущен: "),
    ("Student: ", "Ученик: "),
    ("phases ", "фазы "),
    ("student ", "ученик "),
    ("PASSWORD RESET REQUIRED", "ТРЕБУЕТСЯ СМЕНА ПАРОЛЯ"),
    ("Principal Admin", "Главный администратор"),
    ("Teacher", "Учитель"),
    ("Student", "Ученик"),
    ("Lesson", "Урок"),
    ("Exam", "Экзамен"),
    ("Base Gameplay & Geometry", "Базовый геймплей и геометрия"),
    ("Advanced Mechanics & Speed Dynamics", "Продвинутая механика и динамика скорости"),
    ("Higher League Outline Structures", "Продвинутые структуры и контуры"),
    ("Mega-Mechanics 2.2 & Duals", "Мега-механики 2.2 и дуалы"),
    ("Logic, Coding & Trigger Wizardry", "Логика, кодинг и триггеры"),
    ("Low-Extreme Hardcore & Asymmetrical Duals", "Low-Extreme Hardcore и асимметричные дуалы"),
    ("Art & Decoration Academy", "Академия арта и декора"),
    ("rows  •  ", "строк  •  "),
    ("grade cols", "столбцов оценок"),
    ("LESSONS", "УРОКОВ"),
    ("COMPLETE", "ЗАВЕРШЕНО"),
    ("Control plane", "Панель управления"),
    ("default ×", "по умолчанию ×"),
    (" grades", " оценок"),
]

# Complete RU localization for runtime/system messages, validation errors and dialogs.
RU_TEXT.update({
    "Access denied": "Доступ запрещён",
    "Only the Principal Administrator can manage accounts and teacher invites.": "Управлять аккаунтами и приглашениями учителей может только главный администратор.",
    "You cannot edit submissions for this lesson.": "У вас нет прав изменять данные по этому уроку.",
    "Level ID": "ID уровня",
    "Showcase URL": "Ссылка на showcase",
    "Grade": "Оценка",
    "Delete grade": "Удалить оценку",
    "Delete this grade transaction?": "Удалить эту запись оценки?",
    "New student": "Новый ученик",
    "Only the Principal Administrator can create additional student profiles.": "Создавать дополнительные профили учеников может только главный администратор.",
    "Legacy import": "Импорт старых данных",
    "Legacy GPA import is restricted to the Principal Administrator.": "Импорт старого GPA доступен только главному администратору.",
    "Create or select a student first.": "Сначала создайте или выберите ученика.",
    "Analytics": "Аналитика",
    "Your account cannot modify graduation controls.": "У вашего аккаунта нет прав изменять параметры выпуска.",
    "Your account cannot modify moderator requests.": "У вашего аккаунта нет прав изменять запросы модераторам.",
    "Only the Principal Administrator can create teacher invitations.": "Создавать приглашения для учителей может только главный администратор.",
    "Teacher invite": "Приглашение учителя",
    "Invite": "Приглашение",
    "Account": "Аккаунт",
    "Role": "Роль",
    "Password reset": "Сброс пароля",
    "Database backup is restricted to the Principal Administrator.": "Создавать резервные копии базы может только главный администратор.",
    "Backup": "Резервная копия",
    "Refresh students": "Обновление учеников",
    "Missing UI dependency": "Не установлена библиотека интерфейса",
    "Recovery code regenerated": "Контрольный код перевыпущен",
    "Graduation exam score saved": "Оценка выпускного экзамена сохранена",
    "authorized_phases cannot be empty.": "Нужно выбрать хотя бы одну фазу доступа.",
    "Geometry Dash Level ID must be an 8- or 9-digit positive numeric ID.": "ID уровня Geometry Dash должен состоять из 8 или 9 цифр и быть положительным числом.",
    "Showcase URL must use http:// or https://.": "Ссылка на showcase должна начинаться с http:// или https://.",
    "Showcase URL is malformed.": "Некорректная ссылка на showcase.",
    "Showcase URL must point to YouTube, Shorts, or TikTok.": "Ссылка на showcase должна вести на YouTube, YouTube Shorts или TikTok.",
    "Unable to allocate a unique invitation code.": "Не удалось создать уникальный код приглашения.",
    "This role does not have grading access for this phase.": "У этой роли нет права выставлять оценки в данной фазе.",
    "Grade must be between 0 and 10.": "Оценка должна быть от 0 до 10.",
    "No active student selected.": "Активный ученик не выбран.",
    "Weight multiplier must be x1, x2, x3, or x4.": "Множитель веса должен быть x1, x2, x3 или x4.",
    "Grade no longer exists.": "Эта запись оценки больше не существует.",
    "Baseline must be a finite value between 0 and 10.": "Исходный GPA должен быть числом от 0 до 10.",
    "No active student.": "Нет активного ученика.",
    "Historical lesson weights are invalid.": "Некорректные веса исторических уроков.",
    "Unable to construct the requested baseline within grade bounds.": "Невозможно восстановить указанный исходный GPA в допустимых пределах оценок.",
    "Unable to preserve exact baseline after numeric normalization.": "Не удалось сохранить точный исходный GPA после нормализации чисел.",
    "Weight must be 1, 2, 3, or 4.": "Вес должен быть 1, 2, 3 или 4.",
    "Age is outside the supported range.": "Возраст находится вне допустимого диапазона.",
    "model must be an AcademyModel instance.": "Внутренняя ошибка: модель должна быть экземпляром AcademyModel.",
    "target_gpa must be between 0 and 10.": "Целевой GPA должен быть от 0 до 10.",
    "CustomTkinter is required for the authentication gateway.": "Для экрана авторизации требуется библиотека CustomTkinter.",
    "CustomTkinter is required. Install it with: python3 -m pip install customtkinter pillow": "Требуется библиотека CustomTkinter. Установите её командой: python3 -m pip install customtkinter pillow",
    "Shared database is temporarily unavailable. Try again.": "Общая база данных временно недоступна. Повторите попытку.",
    "Only an administrator can perform this operation.": "Эту операцию может выполнить только администратор.",
    "The last active administrator cannot be demoted.": "Нельзя понизить роль последнего активного администратора.",
    "The last active administrator cannot be disabled.": "Нельзя отключить последнего активного администратора.",
    "You cannot disable the administrator account currently in use.": "Нельзя отключить аккаунт администратора, под которым вы сейчас вошли.",
    "Change your own administrator role from another administrator account.": "Изменяйте роль своего аккаунта администратора из другого администраторского аккаунта.",
    "Role must be ADMIN, TEACHER, or STUDENT.": "Роль должна быть ADMIN, TEACHER или STUDENT.",
    "This account does not require a forced password change.": "Для этого аккаунта не требуется принудительная смена пароля.",
    "Temporary password is incorrect.": "Неверный временный пароль.",
    "New password must be different from the current password.": "Новый пароль должен отличаться от текущего.",
    "Administrator accounts can only be created through Principal Setup.": "Аккаунт администратора можно создать только через настройку главного администратора.",
    "Administrator registration is already closed for this installation.": "Регистрация администратора для этой установки уже закрыта.",
    "Principal Admin already exists.": "Главный администратор уже существует.",
    "Type PRINCIPAL in the setup confirmation field.": "Введите PRINCIPAL в поле подтверждения настройки.",
    "Recovery failed. Check the username and recovery code, or try again later.": "Восстановление не удалось. Проверьте логин и контрольный код либо повторите попытку позже.",
    "Recovery failed. Check the username and security answer, or try again later.": "Восстановление не удалось. Проверьте логин и ответ на контрольный вопрос либо повторите попытку позже.",
    "Recovery code must contain 8 code characters.": "Контрольный код должен содержать 8 символов кода.",
    "Security answer is invalid.": "Неверный ответ на контрольный вопрос.",
    "Invite code is invalid.": "Неверный код приглашения.",
    "Invite code has already been used.": "Этот код приглашения уже использован.",
    "Invite code has been disabled by an administrator.": "Этот код приглашения отключён администратором.",
    "Invite code not found.": "Код приглашения не найден.",
    "Account not found.": "Аккаунт не найден.",
    "Account not found or disabled.": "Аккаунт не найден или отключён.",
    "Invalid username or password.": "Неверный логин или пароль.",
    "This username is already registered.": "Этот логин уже зарегистрирован.",
    "Username must contain 3–32 characters.": "Логин должен содержать от 3 до 32 символов.",
    "Username may contain letters, numbers, dot, underscore, and hyphen only.": "Логин может содержать только буквы, цифры, точку, подчёркивание и дефис.",
    "Password must contain at least 8 characters.": "Пароль должен содержать не менее 8 символов.",
    "Password is too long.": "Пароль слишком длинный.",
    "Passwords do not match.": "Пароли не совпадают.",
    "Current password is incorrect.": "Неверный текущий пароль.",
    "Display name is required.": "Укажите отображаемое имя.",
    "Age must be a whole number.": "Возраст должен быть целым числом.",
    "Manual refresh failed": "Не удалось выполнить ручное обновление",
    "Journal view reset": "Вид журнала сброшен",
    "No students": "Нет учеников",
    "No student": "Ученик не выбран",
    "Lesson not found": "Урок не найден",
    "Administrator access required": "Требуются права администратора",
    "Graduation dossier": "Выпускное досье",
    "Phase": "Фаза",
    "Module": "Модуль",
    "Completion": "Прогресс",
    "Grades": "Оценки",
    "Solo exam": "Сольный экзамен",
    "ACA Graduation Report": "Выпускной отчёт ACA",
})

RU_SUBSTRINGS.extend([
    (" must be numeric.", " должно быть числом."),
    (" must be finite.", " должно быть конечным числом."),
    ("Invalid phase values: ", "Недопустимые номера фаз: "),
    ("Curriculum must contain 120 lessons, got ", "Программа должна содержать 120 уроков; сейчас: "),
    ("Legacy import verification failed: requested ", "Проверка импорта не пройдена: требовалось "),
    (", got ", ", получено "),
    ("Unknown lesson ID: ", "Неизвестный ID урока: "),
    ("Unknown student: ", "Неизвестный ученик: "),
    ("Invite code rejected: ", "Код приглашения отклонён: "),
    (" cannot grade Phase ", " не может выставлять оценки в фазе "),
    ("Backfill complete. GPA = ", "Восстановление завершено. GPA = "),
    ("Save this new recovery code:", "Сохраните новый контрольный код:"),
    ("The previous recovery code is now invalid.", "Предыдущий контрольный код теперь недействителен."),
    ("It has been copied to the clipboard.", "Код скопирован в буфер обмена."),
    ("Temporary password:", "Временный пароль:"),
    ("The user must change it at next sign-in.", "Пользователь должен сменить его при следующем входе."),
    ("Temporary password reset; copied to clipboard", "Временный пароль сброшен и скопирован в буфер обмена"),
    ("Graduation exam score saved", "Оценка выпускного экзамена сохранена"),
    ("ACA Platform requires CustomTkinter.", "Для ACA Platform требуется CustomTkinter."),
    ("Install once with:", "Установите один раз командой:"),
    ("Only the Principal Administrator", "Только главный администратор"),
    ("Save this recovery code somewhere private:", "Сохраните этот контрольный код в надёжном месте:"),
    ("The code is not stored in readable form and will not be shown again.", "Код не хранится в открытом виде и больше не будет показан."),
    ("It is replaced after each password recovery or password change.", "Он заменяется после каждого восстановления или смены пароля."),
    (" • double-click to append grade", " • двойной щелчок — добавить оценку"),
    (" • Grade ", " • Оценка "),
    (" • weight ×", " • вес ×"),
    (" • double-click to edit", " • двойной щелчок — изменить"),
    (" • empty grade slot • double-click to add", " • пустая ячейка оценки • двойной щелчок — добавить"),
    (" cannot grade Фаза ", " не может выставлять оценки в фазе "),
])

def set_ui_language(language):
    global UI_LANGUAGE
    UI_LANGUAGE = "ru" if str(language or "ru").lower().startswith("ru") else "en"

def tr(text):
    if text is None or UI_LANGUAGE != "ru":
        return text
    value = str(text)
    # KeyError.__str__ wraps string payloads in quotes; strip them for user-facing text.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        inner = value[1:-1]
        if inner in RU_TEXT:
            return RU_TEXT[inner]
        value = inner
    if value in RU_TEXT:
        return RU_TEXT[value]
    out = value
    for old, new in RU_SUBSTRINGS:
        out = out.replace(old, new)
    return out


def tr_error(error):
    """Translate an exception or runtime error without leaking KeyError repr quotes."""
    if UI_LANGUAGE != "ru":
        return str(error)
    if isinstance(error, BaseException) and getattr(error, "args", None):
        if len(error.args) == 1 and isinstance(error.args[0], str):
            return tr(error.args[0])
    return tr(str(error))


def language_code_from_ui(value):
    """Normalize the compact UI selector value to a persisted language code."""
    return "ru" if str(value or "").strip().upper().startswith("RU") else "en"


def language_selector_value():
    return "RU" if UI_LANGUAGE == "ru" else "EN"


def language_display_value():
    """Human-readable current language badge used next to RU/EN selectors."""
    return "🇷🇺  Русский" if UI_LANGUAGE == "ru" else "🇬🇧  English"


def tooltip_text(key):
    table = RU_TOOLTIPS if UI_LANGUAGE == "ru" else EN_TOOLTIPS
    return table.get(str(key), str(key))


def localize_lesson_name(name):
    value = str(name or "")
    return LESSON_RU.get(value, value) if UI_LANGUAGE == "ru" else value


def localize_assessment_type(value):
    value = str(value or "")
    return tr(value)


def canonical_assessment_type(value):
    value = str(value or "")
    if UI_LANGUAGE == "ru":
        for internal in (
            "Class participation / live quizzes",
            "Homework layouts",
            "Advanced milestones / complex duals / triggers",
            "Final Graduation Exam",
        ):
            if value == tr(internal):
                return internal
    return value


def role_display_value(role):
    role = str(role or "STUDENT").upper()
    return tr(role)


def role_code_from_display(value):
    value = str(value or "")
    for role in ("STUDENT", "TEACHER", "ADMIN"):
        if value == role or value == tr(role):
            return role
    return value.upper()


def track_display_value(track):
    value = str(track or "")
    return tr(value)


def canonical_track_value(track):
    value = str(track or "").strip()
    if UI_LANGUAGE == "ru":
        reverse = {tr("Gameplay"): "Gameplay", tr("Decoration"): "Decoration"}
        return reverse.get(value, value)
    return value


def localized_grade_count(count):
    count = int(count or 0)
    if UI_LANGUAGE != "ru":
        return f"{count} grade" if count == 1 else f"{count} grades"
    n10, n100 = count % 10, count % 100
    if n10 == 1 and n100 != 11:
        word = "оценка"
    elif n10 in (2, 3, 4) and n100 not in (12, 13, 14):
        word = "оценки"
    else:
        word = "оценок"
    return f"{count} {word}"


RU_MONTHS_GENITIVE = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
RU_MONTHS_NOMINATIVE = (
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)
EN_MONTHS = (
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
EN_MONTHS_SHORT = (
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
RU_MONTHS_SHORT = (
    "", "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
)


def _coerce_datetime(value):
    """Convert ISO strings, unix timestamps, or datetime objects for display only."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc).astimezone()
        except (ValueError, OSError, OverflowError):
            return None
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is not None:
        try:
            dt = dt.astimezone()
        except (ValueError, OSError):
            pass
    return dt


def localized_month_name(month, short=False):
    """Localized standalone month name. Month is 1..12."""
    try:
        month = int(month)
    except (TypeError, ValueError):
        return ""
    if not 1 <= month <= 12:
        return ""
    if UI_LANGUAGE == "ru":
        return RU_MONTHS_SHORT[month] if short else RU_MONTHS_NOMINATIVE[month]
    return EN_MONTHS_SHORT[month] if short else EN_MONTHS[month]


def format_time_localized(value, with_seconds=False):
    dt = _coerce_datetime(value)
    if dt is None:
        return "—"
    if UI_LANGUAGE == "ru":
        return f"{dt.hour:02d}:{dt.minute:02d}" + (f":{dt.second:02d}" if with_seconds else "")
    hour12 = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    base = f"{hour12}:{dt.minute:02d}"
    if with_seconds:
        base += f":{dt.second:02d}"
    return f"{base} {suffix}"


def format_date_localized(value, short=False):
    dt = _coerce_datetime(value)
    if dt is None:
        return "—"
    if UI_LANGUAGE == "ru":
        if short:
            return f"{dt.day:02d}.{dt.month:02d}.{dt.year:04d}"
        return f"{dt.day} {RU_MONTHS_GENITIVE[dt.month]} {dt.year}"
    if short:
        return f"{dt.month:02d}/{dt.day:02d}/{dt.year:04d}"
    return f"{EN_MONTHS[dt.month]} {dt.day}, {dt.year}"


def format_datetime_localized(value, with_seconds=False, short_date=False):
    dt = _coerce_datetime(value)
    if dt is None:
        return "—"
    return f"{format_date_localized(dt, short=short_date)}, {format_time_localized(dt, with_seconds=with_seconds)}"


def format_relative_date_localized(value):
    """Compact date/time for dense account and audit metadata."""
    dt = _coerce_datetime(value)
    if dt is None:
        return "—"
    now = datetime.now().astimezone() if datetime.now().astimezone().tzinfo else datetime.now()
    local = dt.astimezone() if dt.tzinfo is not None else dt
    if local.date() == now.date():
        return (("Сегодня, " if UI_LANGUAGE == "ru" else "Today, ") + format_time_localized(local))
    return format_datetime_localized(local)



def unix_now():
    return int(datetime.now(timezone.utc).timestamp())


def _finite_number(value, field_name="value"):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.")
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _normalize_phase_list(phases):
    normalized = sorted({int(p) for p in (phases or [])})
    if not normalized:
        raise ValueError("authorized_phases cannot be empty.")
    invalid = [p for p in normalized if p not in VALID_PHASES]
    if invalid:
        raise ValueError(f"Invalid phase values: {invalid}")
    return normalized


def _sanitize_level_id(level_id):
    if level_id is None or str(level_id).strip() == "":
        return None
    raw = str(level_id).strip()
    if not raw.isdigit() or len(raw) not in (8, 9) or raw.startswith("0"):
        raise ValueError("Geometry Dash Level ID must be an 8- or 9-digit positive numeric ID.")
    return raw


def _sanitize_showcase_url(url):
    if url is None or str(url).strip() == "":
        return None
    raw = str(url).strip()
    lower = raw.lower()
    if not (lower.startswith("https://") or lower.startswith("http://")):
        raise ValueError("Showcase URL must use http:// or https://.")
    if len(raw) > 2048 or any(ch in raw for ch in ("\n", "\r", "\t", " ")):
        raise ValueError("Showcase URL is malformed.")
    host = raw.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0].lower()
    if host.startswith("www."):
        host = host[4:]
    allowed = (
        host == "youtu.be"
        or host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "tiktok.com"
        or host.endswith(".tiktok.com")
    )
    if not allowed:
        raise ValueError("Showcase URL must point to YouTube, Shorts, or TikTok.")
    return raw


def _default_assessment_weight(index, phase, name):
    if index == 120:
        return 4
    if phase in (5, 6) or "Exam" in name or "Master Review" in name:
        return 3
    if index == 2 or phase == 7:
        return 2
    return 1


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def build_curriculum():
    phases = [
        (1, "Base Gameplay & Geometry", 1.0, [
            "Balance", "Solid Structuring", "Ship Physics", "Musical Sync",
            "Slopes", "Ball / Robot", "UFO Control",
        ]),
        (2, "Advanced Mechanics & Speed Dynamics", 1.2, [
            "Wave Basics", "Alpha Readability", "Gravity Portals", "Speed Changes",
            "Orbs on Ship / Wave", "Upside-Down", "Teleports", "Mechanics Integration Review",
        ]),
        (3, "Higher League Outline Structures", 1.5, [
            "Outline Weights", "Air Contours", "Jitter / Click Variety", "Layout Readability",
            "Timings / Fakes", "Sightread Test", "Cherry Team Workflow", "Hitbox Stress Test",
        ]),
        (4, "Mega-Mechanics 2.2 & Duals", 1.8, [
            "Spider Teleport", "Swingcopter", "2.2 Triggers", "Symmetrical Duals",
            "Mirror Duals", "Layout Stitching", "Gameplay Exam",
        ]),
        (5, "Logic, Coding & Trigger Wizardry", 2.0, [
            "Move Trigger Fundamentals", "Rotate Trigger Fundamentals", "Follow Trigger", "Lock Systems",
            "Camera Zoom", "Camera Rotate", "Camera Edge", "Spawn Trigger", "Toggle Networks",
            "Touch Trigger", "Count Trigger", "Item IDs", "Pickup / Persistent Counters",
            "If / Else Conditional Logic", "Multi-Condition Logic", "State Machines",
            "Bossfight Motion Logic", "Bossfight Damage Logic", "Bossfight Phase Logic",
            "Shader & Visual Trigger Integration", "Event Trigger Chains", "Optimization of Trigger Groups",
            "Debugging Trigger Race Conditions", "Custom Bossfight", "Trigger Exam",
        ]),
        (6, "Low-Extreme Hardcore & Asymmetrical Duals", 2.5, [
            "Extreme Balance", "Fast Switches", "Dual Hitboxes", "Cube + Ball Dual",
            "Ship + Robot Dual", "Fast-Click Drops", "60Hz Bug Fixing", "144Hz Bug Fixing",
            "240Hz Bug Fixing", "Extreme Verification",
        ]),
    ]

    phase7_names = [
        "Color Theory I", "Color Theory II", "Palette Hierarchy", "Blending Modes", "Gradient Control",
        "Pulse Sync Basics", "Pulse Sync Advanced", "Beat-Driven Color Automation", "Glow Fundamentals",
        "Glow Layering", "Shading Fundamentals", "Directional Lighting", "Ambient Occlusion Illusion",
        "Air Deco Basics", "Air Deco Density", "Negative Space Control", "Block Design I", "Block Design II",
        "Block Design III", "Material Language", "Texture Rhythm", "Edge Detailing", "Foreground Framing",
        "Background Composition", "Custom Backgrounds", "Parallax I", "Parallax II", "Depth Separation",
        "Particle Language", "Atmospheric FX", "Fog & Bloom Simulation", "Motion Decoration",
        "Decorative Trigger Choreography", "Color Channel Systems", "Object Group Architecture",
        "Theme Consistency Review", "Readability Under Decoration", "Gameplay / Deco Alignment",
        "LDM Planning", "LDM Optimization", "Object Count Optimization", "Draw-Call Awareness",
        "Performance Audit", "Transition Polish", "Section Stitching", "Megacollab Handoff Standards",
        "Megacollab Style Matching", "Megacollab Polish I", "Megacollab Polish II", "Final Art Direction",
        "Presentation Capture", "Portfolio Packaging", "Moderator Readiness", "Phase 7 Master Review",
        "Art & Decoration Graduation Exam",
    ]
    phases.append((7, "Art & Decoration Academy", 1.5, phase7_names))

    lessons = []
    idx = 1
    for phase_num, phase_name, weight, names in phases:
        for name in names:
            lessons.append({
                "id": f"L{idx:02d}",
                "index": idx,
                "phase": phase_num,
                "phase_name": phase_name,
                "name": name,
                "type": "Exam" if "Exam" in name or "Review" in name else "Lesson",
                "weight": weight,
                "default_assessment_weight": _default_assessment_weight(idx, phase_num, name),
            })
            idx += 1
    if len(lessons) != 120:
        raise RuntimeError(f"Curriculum must contain 120 lessons, got {len(lessons)}")
    return lessons


CURRICULUM = build_curriculum()
LESSON_BY_ID = {lesson["id"]: lesson for lesson in CURRICULUM}


class DataStore:
    def __init__(self, path=DB_FILE):
        self.path = os.path.abspath(path)
        self.data = None
        self._last_file_signature = None
        self.load_or_create()

    def _default_data(self):
        return {
            "meta": {
                "app": APP_TITLE,
                "version": APP_VERSION,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
            "settings": {
                "probation_threshold": 8.90,
                "team_threshold": 9.30,
                "homework_penalty": 0.25,
                "active_user_role": "HOST",
                "active_student_id": None,
                "language": "ru",
                "moderator_requests": {
                    "gameplay": False,
                    "art": False,
                    "verification": False,
                },
            },
            "students": {},
            "accounts": {},
            "auth_audit": [],
            "teacher_invites": {},
            "teacher_sessions": {},
            "notifications": [],
            "audit_log": [],
        }

    def load_or_create(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self._migrate()
                return
            except (OSError, json.JSONDecodeError):
                broken = self.path + ".broken_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                try:
                    os.replace(self.path, broken)
                except OSError:
                    pass
        self.data = self._default_data()
        self.save()

    def _migrate(self, persist=True):
        default = self._default_data()
        self.data.setdefault("meta", default["meta"])
        self.data.setdefault("settings", default["settings"])
        self.data.setdefault("students", {})
        self.data.setdefault("accounts", {})
        self.data.setdefault("auth_audit", [])
        self.data.setdefault("teacher_invites", {})
        self.data.setdefault("teacher_sessions", {})
        self.data.setdefault("notifications", [])
        self.data.setdefault("audit_log", [])
        for k, v in default["settings"].items():
            self.data["settings"].setdefault(k, v)
        for sid, student in self.data["students"].items():
            student.setdefault("lesson_records", {})
            student.setdefault("attendance_skips", 0)
            student.setdefault("homework_skips", 0)
            student.setdefault("active_tracks", ["Gameplay", "Decoration"])
            student.setdefault("created_at", now_iso())
            student.setdefault("skill_class", "Unranked")
            student.setdefault("age", 0)
            student.setdefault("legacy_import", None)

            # v1.1 journal migration: every lesson owns an unlimited list of grade
            # transactions.  Older databases stored one grade directly on the lesson
            # record; convert that value losslessly on first load.
            for lesson_id, rec in list(student["lesson_records"].items()):
                if not isinstance(rec, dict):
                    student["lesson_records"][lesson_id] = {"grades": [], "status": "Not Started"}
                    continue
                grades = rec.get("grades")
                if not isinstance(grades, list):
                    grades = []
                    if rec.get("grade") is not None:
                        grades.append({
                            "grade_id": uuid.uuid4().hex,
                            "grade": float(rec.get("grade", 0.0)),
                            "effective_grade": float(rec.get("effective_grade", rec.get("grade", 0.0))),
                            "homework_skipped": bool(rec.get("homework_skipped", False)),
                            "homework_status": "skipped" if rec.get("homework_skipped") else "not_applicable",
                            "weight_multiplier": 1,
                            "assessment_type": "MIGRATED",
                            "timestamp": rec.get("timestamp", now_iso()),
                            "unix_timestamp": unix_now(),
                            "graded_by": rec.get("graded_by", "MIGRATED"),
                        })
                normalized = []
                for entry in grades:
                    if isinstance(entry, (int, float)):
                        raw = float(entry)
                        normalized.append({
                            "grade_id": uuid.uuid4().hex,
                            "grade": raw,
                            "effective_grade": raw,
                            "homework_skipped": False,
                            "homework_status": "not_applicable",
                            "weight_multiplier": 1,
                            "assessment_type": "MIGRATED",
                            "timestamp": now_iso(),
                            "unix_timestamp": unix_now(),
                            "graded_by": "MIGRATED",
                        })
                    elif isinstance(entry, dict) and entry.get("grade") is not None:
                        raw = float(entry.get("grade", 0.0))
                        normalized.append({
                            "grade_id": entry.get("grade_id") or uuid.uuid4().hex,
                            "grade": raw,
                            "effective_grade": float(entry.get("effective_grade", raw)),
                            "homework_skipped": bool(entry.get("homework_skipped", False)),
                            "homework_status": entry.get("homework_status", "skipped" if entry.get("homework_skipped") else "not_applicable"),
                            "weight_multiplier": int(entry.get("weight_multiplier", 1)),
                            "assessment_type": entry.get("assessment_type", "MIGRATED"),
                            "timestamp": entry.get("timestamp", now_iso()),
                            "unix_timestamp": int(entry.get("unix_timestamp", unix_now())),
                            "graded_by": entry.get("graded_by", "MIGRATED"),
                        })
                rec["grades"] = normalized
                rec["status"] = "Passed" if normalized else "Not Started"
                rec["timestamp"] = normalized[-1]["timestamp"] if normalized else rec.get("timestamp", "")
                rec["level_id_link"] = _sanitize_level_id(rec.get("level_id_link"))
                rec["showcase_pipeline_url"] = _sanitize_showcase_url(rec.get("showcase_pipeline_url"))
                # Obsolete single-grade transaction lock is intentionally removed.
                rec.pop("locked", None)

            student["homework_skips"] = sum(
                1
                for rec in student["lesson_records"].values()
                if isinstance(rec, dict)
                for entry in rec.get("grades", [])
                if isinstance(entry, dict) and entry.get("homework_skipped")
            )
        self.data["meta"]["version"] = APP_VERSION
        if persist:
            self.data["meta"]["updated_at"] = now_iso()
            self.save()

    @staticmethod
    def _sync_in_place(target, source):
        """Replace JSON-compatible data while preserving shared object identities.

        AuthenticationManager and TeacherOnboardingManager intentionally keep
        references to top-level dictionaries. Mutating those containers in place
        lets every service immediately see a cross-process database reload.
        """
        if isinstance(target, dict) and isinstance(source, dict):
            for key in list(target.keys()):
                if key not in source:
                    del target[key]
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    DataStore._sync_in_place(target[key], value)
                elif key in target and isinstance(target[key], list) and isinstance(value, list):
                    DataStore._sync_in_place(target[key], value)
                else:
                    target[key] = value
            return
        if isinstance(target, list) and isinstance(source, list):
            target[:] = source

    def _file_signature(self):
        try:
            st = os.stat(self.path)
            return (int(st.st_mtime_ns), int(st.st_size))
        except OSError:
            return None

    def _reload_from_disk(self, force=False):
        """Reload the shared JSON database into the current object graph.

        ``force=False`` is used by the 120 ms watcher and avoids disk reads when
        the file signature has not changed. ``force=True`` is reserved for the
        manual refresh control and always re-reads the database.
        """
        signature = self._file_signature()
        if signature is None:
            return False
        if not force and signature == self._last_file_signature:
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                incoming = json.load(f)
            if not isinstance(incoming, dict):
                return False
        except (OSError, json.JSONDecodeError):
            # A writer may be between filesystem operations. Keep the current
            # in-memory snapshot; live-sync will retry on the next polling tick.
            return False

        current = self.data
        self.data = incoming
        try:
            self._migrate(persist=False)
            incoming = self.data
        finally:
            self.data = current
        self._sync_in_place(current, incoming)
        self._last_file_signature = signature
        return True

    def reload_if_changed(self):
        """Reload changes written by another ACA Platform process when needed."""
        return self._reload_from_disk(force=False)

    def force_reload(self):
        """Unconditionally re-read the shared database for manual recovery."""
        return self._reload_from_disk(force=True)

    def save(self):
        self.data["meta"]["updated_at"] = now_iso()
        tmp = self.path + ".tmp." + str(os.getpid())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, self.path)
        self._last_file_signature = self._file_signature()

    def backup(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        target = os.path.join(BACKUP_DIR, "aca_system_db_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return target


class AcademyModel:
    def __init__(self, store):
        self.store = store

    @property
    def students(self):
        return self.store.data["students"]

    @property
    def settings(self):
        return self.store.data["settings"]

    def add_student(self, name, age, skill_class, active_tracks):
        sid = "S" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.students[sid] = {
            "id": sid,
            "name": name.strip(),
            "age": int(age),
            "skill_class": skill_class.strip() or "Unranked",
            "active_tracks": active_tracks or ["Gameplay"],
            "attendance_skips": 0,
            "homework_skips": 0,
            "created_at": now_iso(),
            "legacy_import": None,
            "lesson_records": {},
        }
        self.settings["active_student_id"] = sid
        self.store.save()
        return sid

    def delete_student(self, sid):
        if sid in self.students:
            del self.students[sid]
            if self.settings.get("active_student_id") == sid:
                self.settings["active_student_id"] = next(iter(self.students), None)
            self.store.save()

    def get_student(self, sid=None):
        sid = sid or self.settings.get("active_student_id")
        return self.students.get(sid)

    def set_active_student(self, sid):
        # Persist only when the active student actually changes.
        # Re-saving an unchanged selection from a Treeview callback can create
        # an event/save/refresh feedback loop on Tk/macOS.
        if sid not in self.students:
            return False
        if self.settings.get("active_student_id") == sid:
            return False
        self.settings["active_student_id"] = sid
        self.store.save()
        return True

    def get_record(self, sid, lesson_id):
        student = self.get_student(sid)
        if not student:
            return None
        return student["lesson_records"].get(lesson_id)

    def _grade_entries(self, rec):
        if not rec or not isinstance(rec, dict):
            return []
        grades = rec.get("grades")
        if isinstance(grades, list):
            return [g for g in grades if isinstance(g, dict) and g.get("grade") is not None]
        # Runtime compatibility for a database that has not yet been migrated.
        if rec.get("grade") is not None:
            raw = float(rec.get("grade", 0.0))
            return [{
                "grade_id": rec.get("grade_id") or uuid.uuid4().hex,
                "grade": raw,
                "effective_grade": float(rec.get("effective_grade", raw)),
                "homework_skipped": bool(rec.get("homework_skipped", False)),
                "homework_status": "skipped" if rec.get("homework_skipped") else "not_applicable",
                "weight_multiplier": int(rec.get("weight_multiplier", 1)),
                "assessment_type": rec.get("assessment_type", "MIGRATED"),
                "timestamp": rec.get("timestamp", ""),
                "unix_timestamp": int(rec.get("unix_timestamp", unix_now())),
                "graded_by": rec.get("graded_by", "MIGRATED"),
            }]
        return []

    def get_grades(self, sid, lesson_id):
        return list(self._grade_entries(self.get_record(sid, lesson_id)))

    def active_lesson_id(self, sid):
        student = self.get_student(sid)
        if not student:
            return None
        for lesson in CURRICULUM:
            rec = student["lesson_records"].get(lesson["id"])
            if not self._grade_entries(rec):
                return lesson["id"]
        return None

    def can_edit_phase(self, role, phase):
        if isinstance(role, dict):
            role_name = str(role.get("role", "")).upper()
            if role_name == "ADMIN":
                return True
            if role_name == "TEACHER":
                return int(phase) in {int(p) for p in role.get("authorized_phases", [])}
            return False
        if role in ("HOST", "ADMIN", "PRINCIPAL_ADMIN"):
            return True
        if role in ("DECO", "TEACHER_PHASE7"):
            return int(phase) == 7
        return False

    @staticmethod
    def actor_label(role):
        if isinstance(role, dict):
            return str(role.get("display_name") or role.get("username") or role.get("role") or "USER")
        return str(role or "SYSTEM")

    def submit_grade(self, sid, lesson_id, grade, homework_skipped=False, role="HOST",
                     weight_multiplier=None, assessment_type=None):
        lesson = LESSON_BY_ID[lesson_id]
        if not self.can_edit_phase(role, lesson["phase"]):
            raise PermissionError("This role does not have grading access for this phase.")
        grade = _finite_number(grade, "Grade")
        if not (0.0 <= grade <= 10.0):
            raise ValueError("Grade must be between 0 and 10.")
        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student selected.")

        multiplier = int(lesson.get("default_assessment_weight", 1) if weight_multiplier is None else weight_multiplier)
        if multiplier not in VALID_ASSESSMENT_WEIGHTS:
            raise ValueError("Weight multiplier must be x1, x2, x3, or x4.")
        assessment_type = str(assessment_type or GradeWeightPolicy.LABELS[multiplier]).strip()

        penalty = float(self.settings.get("homework_penalty", 0.25)) if homework_skipped else 0.0
        effective = clamp(grade - penalty, 0.0, 10.0)
        rec = student["lesson_records"].setdefault(lesson_id, {
            "grades": [], "status": "Not Started", "level_id_link": None, "showcase_pipeline_url": None
        })
        if not isinstance(rec.get("grades"), list):
            rec["grades"] = self._grade_entries(rec)
        entry = {
            "grade_id": uuid.uuid4().hex,
            "grade": round(grade, 4),
            "effective_grade": round(effective, 4),
            "homework_skipped": bool(homework_skipped),
            "homework_status": "skipped" if homework_skipped else "submitted",
            "weight_multiplier": multiplier,
            "assessment_type": assessment_type,
            "timestamp": now_iso(),
            "unix_timestamp": unix_now(),
            "graded_by": self.actor_label(role),
        }
        rec["grades"].append(entry)
        rec["status"] = "Passed"
        rec["timestamp"] = entry["timestamp"]
        rec.pop("locked", None)
        if homework_skipped:
            student["homework_skips"] = int(student.get("homework_skips", 0)) + 1
        self._push_notification(sid, "Team Alert: Host modified your GPA! Check your stats", {
            "lesson_id": lesson_id, "grade_id": entry["grade_id"], "score": grade, "weight_multiplier": multiplier
        })
        self._audit(sid, "GRADE_SUBMITTED", lesson_id, {
            "grade_id": entry["grade_id"], "score": grade, "weight_multiplier": multiplier, "assessment_type": assessment_type
        })
        self.store.save()
        return len(rec["grades"]) - 1

    def delete_grade(self, sid, lesson_id, grade_index, role="HOST"):
        lesson = LESSON_BY_ID[lesson_id]
        if not self.can_edit_phase(role, lesson["phase"]):
            raise PermissionError("This role does not have grading access for this phase.")
        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student selected.")
        rec = student["lesson_records"].get(lesson_id)
        entries = self._grade_entries(rec)
        if not rec or grade_index < 0 or grade_index >= len(entries):
            raise IndexError("Grade no longer exists.")
        removed = entries.pop(grade_index)
        rec["grades"] = entries
        rec["status"] = "Passed" if entries else "Not Started"
        rec["timestamp"] = entries[-1].get("timestamp", "") if entries else ""
        if removed.get("homework_skipped"):
            student["homework_skips"] = max(0, int(student.get("homework_skips", 0)) - 1)
        if not entries:
            student["lesson_records"].pop(lesson_id, None)
        self.store.save()

    def clear_lesson_grades(self, sid, lesson_id, role="HOST"):
        lesson = LESSON_BY_ID[lesson_id]
        if not self.can_edit_phase(role, lesson["phase"]):
            raise PermissionError("This role does not have grading access for this phase.")
        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student selected.")
        rec = student["lesson_records"].get(lesson_id)
        if not rec:
            return
        skipped = sum(1 for entry in self._grade_entries(rec) if entry.get("homework_skipped"))
        student["homework_skips"] = max(0, int(student.get("homework_skips", 0)) - skipped)
        student["lesson_records"].pop(lesson_id, None)
        self.store.save()

    def update_grade(self, sid, lesson_id, grade_index, grade, homework_skipped=False, role="HOST",
                     weight_multiplier=None, assessment_type=None):
        lesson = LESSON_BY_ID[lesson_id]
        if not self.can_edit_phase(role, lesson["phase"]):
            raise PermissionError("This role does not have grading access for this phase.")
        grade = _finite_number(grade, "Grade")
        if not (0.0 <= grade <= 10.0):
            raise ValueError("Grade must be between 0 and 10.")
        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student selected.")
        rec = student["lesson_records"].get(lesson_id)
        entries = self._grade_entries(rec)
        if not rec or grade_index < 0 or grade_index >= len(entries):
            raise IndexError("Grade no longer exists.")
        old = entries[grade_index]
        old_skip = bool(old.get("homework_skipped"))
        multiplier = int(old.get("weight_multiplier", lesson.get("default_assessment_weight", 1)) if weight_multiplier is None else weight_multiplier)
        if multiplier not in VALID_ASSESSMENT_WEIGHTS:
            raise ValueError("Weight multiplier must be x1, x2, x3, or x4.")
        assessment_type = str(assessment_type or old.get("assessment_type") or GradeWeightPolicy.LABELS[multiplier]).strip()
        penalty = float(self.settings.get("homework_penalty", 0.25)) if homework_skipped else 0.0
        effective = clamp(grade - penalty, 0.0, 10.0)
        entries[grade_index] = {
            "grade_id": old.get("grade_id") or uuid.uuid4().hex,
            "grade": round(grade, 4),
            "effective_grade": round(effective, 4),
            "homework_skipped": bool(homework_skipped),
            "homework_status": "skipped" if homework_skipped else "submitted",
            "weight_multiplier": multiplier,
            "assessment_type": assessment_type,
            "timestamp": now_iso(),
            "unix_timestamp": unix_now(),
            "graded_by": self.actor_label(role),
        }
        rec["grades"] = entries
        rec["status"] = "Passed" if entries else "Not Started"
        rec["timestamp"] = entries[-1].get("timestamp", "") if entries else ""
        if old_skip != bool(homework_skipped):
            delta = 1 if homework_skipped else -1
            student["homework_skips"] = max(0, int(student.get("homework_skips", 0)) + delta)
        self._push_notification(sid, "Team Alert: Host modified your GPA! Check your stats", {
            "lesson_id": lesson_id, "grade_id": entries[grade_index]["grade_id"], "score": grade, "weight_multiplier": multiplier
        })
        self._audit(sid, "GRADE_UPDATED", lesson_id, {
            "grade_id": entries[grade_index]["grade_id"], "score": grade, "weight_multiplier": multiplier
        })
        self.store.save()

    def total_grade_count(self, sid):
        student = self.get_student(sid)
        if not student:
            return 0
        return sum(len(self._grade_entries(student["lesson_records"].get(l["id"]))) for l in CURRICULUM)

    def _weighted_totals(self, sid, raw=False):
        student = self.get_student(sid)
        if not student:
            return 0.0, 0.0
        weighted_sum = 0.0
        weight_total = 0.0
        for lesson in CURRICULUM:
            rec = student["lesson_records"].get(lesson["id"])
            for entry in self._grade_entries(rec):
                value = float(entry.get("grade", 0.0) if raw else entry.get("effective_grade", entry.get("grade", 0.0)))
                combined_weight = float(lesson["weight"]) * float(entry.get("weight_multiplier", 1))
                weighted_sum += value * combined_weight
                weight_total += combined_weight
        return weighted_sum, weight_total

    def weighted_gpa(self, sid):
        weighted_sum, weight_total = self._weighted_totals(sid)
        return weighted_sum / weight_total if weight_total else 0.0

    def phase_gpa(self, sid, phase):
        student = self.get_student(sid)
        if not student:
            return 0.0
        s = 0.0
        w = 0.0
        for lesson in CURRICULUM:
            if lesson["phase"] != phase:
                continue
            rec = student["lesson_records"].get(lesson["id"])
            for entry in self._grade_entries(rec):
                combined_weight = float(lesson["weight"]) * float(entry.get("weight_multiplier", 1))
                s += float(entry.get("effective_grade", entry.get("grade", 0.0))) * combined_weight
                w += combined_weight
        return s / w if w else 0.0

    def progress(self, sid):
        student = self.get_student(sid)
        if not student:
            return 0.0
        passed = sum(
            1 for lesson in CURRICULUM
            if self._grade_entries(student["lesson_records"].get(lesson["id"]))
        )
        return passed / len(CURRICULUM)

    def badge(self, sid):
        gpa = self.weighted_gpa(sid)
        passed = int(round(self.progress(sid) * 120))
        if passed == 0:
            return "NEW_PROFILE"
        if gpa < float(self.settings.get("probation_threshold", 8.9)):
            return "PROBATION_LOCKED"
        if gpa >= float(self.settings.get("team_threshold", 9.3)):
            return "TEAM_APPROVED"
        return "ACTIVE_CORE"

    def gpa_series(self, sid):
        student = self.get_student(sid)
        if not student:
            return []
        series = []
        s = 0.0
        w = 0.0
        sequence = 0
        for lesson in CURRICULUM:
            rec = student["lesson_records"].get(lesson["id"])
            for entry in self._grade_entries(rec):
                sequence += 1
                combined_weight = float(lesson["weight"]) * float(entry.get("weight_multiplier", 1))
                s += float(entry.get("effective_grade", entry.get("grade", 0.0))) * combined_weight
                w += combined_weight
                series.append((sequence, s / w))
        return series

    def consecutive_tens_needed(self, sid, threshold):
        result = StudentPerformanceAnalytics(self).clutch_gpa_simulator(sid, threshold)
        return result["required_consecutive_tens"] if result["reachable"] else math.inf

    def delinquency_impact(self, sid):
        student = self.get_student(sid)
        if not student:
            return {"skips": 0, "penalty_points": 0.0, "gpa_without_penalty": 0.0, "gpa_current": 0.0}
        s_raw = 0.0
        s_eff = 0.0
        w = 0.0
        skips = 0
        for lesson in CURRICULUM:
            rec = student["lesson_records"].get(lesson["id"])
            for entry in self._grade_entries(rec):
                wt = float(lesson["weight"]) * float(entry.get("weight_multiplier", 1))
                raw = float(entry.get("grade", 0.0))
                eff = float(entry.get("effective_grade", raw))
                s_raw += raw * wt
                s_eff += eff * wt
                w += wt
                skips += int(bool(entry.get("homework_skipped")))
        raw = s_raw / w if w else 0.0
        eff = s_eff / w if w else 0.0
        return {
            "skips": skips,
            "penalty_points": max(0.0, raw - eff),
            "gpa_without_penalty": raw,
            "gpa_current": eff,
        }

    def legacy_backfill(self, sid, baseline, history_count=12):
        """Reconstruct a deterministic historical record with an exact effective weighted GPA.

        The wizard is GUI-only: no console input is used anywhere.  The generated history
        contains a baseline-dependent mix of lower grades and homework skips while keeping
        the weighted effective GPA equal to ``baseline`` (within floating-point tolerance).
        """
        baseline = float(baseline)
        if not math.isfinite(baseline) or not 0.0 <= baseline <= 10.0:
            raise ValueError("Baseline must be a finite value between 0 and 10.")

        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student.")

        history_count = int(clamp(int(history_count), 2, 40))
        selected = CURRICULUM[:history_count]
        penalty = max(0.0, float(self.settings.get("homework_penalty", 0.25)))
        total_weight = sum(float(lesson["weight"]) for lesson in selected)
        if total_weight <= 0.0:
            raise ValueError("Historical lesson weights are invalid.")
        target_sum = baseline * total_weight

        # Lower baselines intentionally produce a larger historical weak-grade cluster.
        # High baselines can legitimately have no synthetic "bad" grades.
        weakness = clamp((7.0 - baseline) / 7.0, 0.0, 1.0)
        low_count = int(round(history_count * (0.10 + 0.55 * weakness))) if baseline < 9.5 else 0
        low_count = min(max(low_count, 0), history_count - 1)

        # Build EFFECTIVE grades first.  That makes the target GPA independent from
        # homework-penalty reconstruction and removes the old impossible-baseline case.
        effective = [baseline for _ in range(history_count)]
        if low_count > 0 and 0.0 < baseline < 10.0:
            low_value = max(0.0, baseline - (0.75 + 1.75 * weakness))
            for i in range(low_count):
                effective[i] = low_value

            deficit = target_sum - sum(effective[i] * selected[i]["weight"] for i in range(history_count))
            for i in range(low_count, history_count):
                if deficit <= 1e-12:
                    break
                wt = float(selected[i]["weight"])
                room = (10.0 - effective[i]) * wt
                step = min(deficit, room)
                effective[i] += step / wt
                deficit -= step

            # If high-grade headroom was insufficient, lift the low cluster until exact.
            if deficit > 1e-12:
                for i in reversed(range(low_count)):
                    wt = float(selected[i]["weight"])
                    room = (baseline - effective[i]) * wt
                    step = min(deficit, room)
                    effective[i] += step / wt
                    deficit -= step
                    if deficit <= 1e-12:
                        break

        # Final floating-point correction directly against effective grades.
        residual = target_sum - sum(effective[i] * selected[i]["weight"] for i in range(history_count))
        if abs(residual) > 1e-12:
            for i in reversed(range(history_count)):
                wt = float(selected[i]["weight"])
                if residual > 0.0:
                    room = (10.0 - effective[i]) * wt
                    step = min(residual, room)
                    effective[i] += step / wt
                    residual -= step
                else:
                    room = effective[i] * wt
                    step = min(-residual, room)
                    effective[i] -= step / wt
                    residual += step
                if abs(residual) <= 1e-12:
                    break
        if abs(residual) > 1e-8:
            raise ValueError("Unable to construct the requested baseline within grade bounds.")

        # Derive a realistic homework-skip count from the weak-history factor.  A skipped
        # lesson can only have an effective grade <= 10-penalty because its raw grade is
        # capped at 10, so only eligible records are selected.  This is what previously
        # made baselines near 10 impossible.
        requested_skip_ratio = clamp(0.62 * weakness, 0.0, 0.62)
        requested_skips = int(round(history_count * requested_skip_ratio))
        eligible = [
            i for i, value in enumerate(effective)
            if penalty <= 0.0 or value <= 10.0 - penalty + 1e-12
        ]
        # Prefer the lowest effective grades as delinquent history.
        eligible.sort(key=lambda i: (effective[i], i))
        skip_indices = set(eligible[:requested_skips])

        raw_grades = []
        for i, value in enumerate(effective):
            raw = value + penalty if i in skip_indices else value
            raw_grades.append(clamp(raw, 0.0, 10.0))

        # Transactional replacement: prepare records first, then swap them into the profile.
        imported_at = now_iso()
        records = {}
        for i, lesson in enumerate(selected):
            is_skip = i in skip_indices
            raw = raw_grades[i]
            eff = clamp(raw - (penalty if is_skip else 0.0), 0.0, 10.0)
            records[lesson["id"]] = {
                "grades": [{
                    "grade_id": uuid.uuid4().hex,
                    "grade": round(raw, 10),
                    "effective_grade": round(eff, 10),
                    "homework_skipped": is_skip,
                    "homework_status": "skipped" if is_skip else "submitted",
                    "weight_multiplier": 1,
                    "assessment_type": "LEGACY_IMPORT",
                    "timestamp": imported_at,
                    "unix_timestamp": unix_now(),
                    "graded_by": "LEGACY_IMPORT",
                }],
                "status": "Passed",
                "timestamp": imported_at,
            }

        # Verify before committing so a failed import never destroys existing history.
        verify_sum = sum(
            records[lesson["id"]]["grades"][0]["effective_grade"] * float(lesson["weight"])
            for lesson in selected
        )
        verify_gpa = verify_sum / total_weight
        if abs(verify_gpa - baseline) > 1e-7:
            # Correct rounding drift on one non-skipped record if possible.
            correction = (baseline - verify_gpa) * total_weight
            corrected = False
            for i in reversed(range(history_count)):
                if i in skip_indices:
                    continue
                lesson = selected[i]
                wt = float(lesson["weight"])
                rec = records[lesson["id"]]["grades"][0]
                candidate = rec["effective_grade"] + correction / wt
                if -1e-12 <= candidate <= 10.0 + 1e-12:
                    candidate = clamp(candidate, 0.0, 10.0)
                    rec["grade"] = candidate
                    rec["effective_grade"] = candidate
                    corrected = True
                    break
            if not corrected:
                raise ValueError("Unable to preserve exact baseline after numeric normalization.")

        student["lesson_records"] = records
        student["homework_skips"] = len(skip_indices)
        student["legacy_import"] = {
            "baseline": baseline,
            "history_count": history_count,
            "low_grade_count": low_count,
            "low_grade_ratio": (low_count / history_count) if history_count else 0.0,
            "homework_skip_count": len(skip_indices),
            "homework_skip_ratio": (len(skip_indices) / history_count) if history_count else 0.0,
            "imported_at": imported_at,
        }
        self.store.save()

        actual = self.weighted_gpa(sid)
        if abs(actual - baseline) > 1e-7:
            raise RuntimeError(f"Legacy import verification failed: requested {baseline:.6f}, got {actual:.6f}.")
        return actual



    def set_level_id_link(self, sid, lesson_id, level_id):
        if lesson_id not in LESSON_BY_ID:
            raise KeyError(f"Unknown lesson ID: {lesson_id}")
        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student selected.")
        value = _sanitize_level_id(level_id)
        rec = student["lesson_records"].setdefault(lesson_id, {"grades": [], "status": "Not Started"})
        rec["level_id_link"] = value
        rec.setdefault("showcase_pipeline_url", None)
        self._audit(sid, "LEVEL_ID_UPDATED", lesson_id, {"level_id_link": value})
        self.store.save()
        return value

    def set_showcase_pipeline_url(self, sid, lesson_id, url):
        if lesson_id not in LESSON_BY_ID:
            raise KeyError(f"Unknown lesson ID: {lesson_id}")
        student = self.get_student(sid)
        if not student:
            raise ValueError("No active student selected.")
        value = _sanitize_showcase_url(url)
        rec = student["lesson_records"].setdefault(lesson_id, {"grades": [], "status": "Not Started"})
        rec["showcase_pipeline_url"] = value
        rec.setdefault("level_id_link", None)
        self._audit(sid, "SHOWCASE_URL_UPDATED", lesson_id, {"showcase_pipeline_url": value})
        self.store.save()
        return value

    def _push_notification(self, sid, message, payload=None):
        item = {
            "notification_id": uuid.uuid4().hex,
            "student_id": sid,
            "message": str(message),
            "payload": payload or {},
            "created_at": now_iso(),
            "unix_timestamp": unix_now(),
            "read": False,
        }
        self.store.data.setdefault("notifications", []).append(item)
        return item

    def _audit(self, sid, action, lesson_id=None, payload=None):
        self.store.data.setdefault("audit_log", []).append({
            "audit_id": uuid.uuid4().hex,
            "student_id": sid,
            "action": str(action),
            "lesson_id": lesson_id,
            "payload": payload or {},
            "created_at": now_iso(),
            "unix_timestamp": unix_now(),
        })


class GradeWeightPolicy:
    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    QUADRUPLE = 4
    LABELS = {
        1: "Class participation / live quizzes",
        2: "Homework layouts",
        3: "Advanced milestones / complex duals / triggers",
        4: "Final Graduation Exam",
    }

    @classmethod
    def validate(cls, weight):
        value = int(weight)
        if value not in VALID_ASSESSMENT_WEIGHTS:
            raise ValueError("Weight must be 1, 2, 3, or 4.")
        return value


class TeacherOnboardingManager:
    """Persistent single-use invite-code and teacher-session manager."""

    def __init__(self, store=None):
        self.store = store
        if store is None:
            self.invite_db = {}
            self.session_db = {}
        else:
            self.invite_db = store.data.setdefault("teacher_invites", {})
            self.session_db = store.data.setdefault("teacher_sessions", {})

    @staticmethod
    def _suffix(seed):
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return "".join(INVITE_ALPHABET[b % len(INVITE_ALPHABET)] for b in digest[:4])

    def _sync_external(self):
        if self.store is not None:
            self.store.reload_if_changed()

    def _save(self):
        if self.store is not None:
            self.store.save()

    def generate_invite_code(self, authorized_phases, teacher_label=None):
        self._sync_external()
        phases = _normalize_phase_list(authorized_phases)
        for _ in range(10000):
            seed = f"{uuid.uuid4()}|{datetime.now(timezone.utc).isoformat()}|{uuid.uuid4().int}|{len(self.invite_db)}"
            code = INVITE_PREFIX + self._suffix(seed)
            if code not in self.invite_db:
                self.invite_db[code] = {
                    "creation_timestamp": unix_now(),
                    "creation_iso": datetime.now(timezone.utc).isoformat(),
                    "is_activated": False,
                    "is_enabled": True,
                    "disabled_timestamp": None,
                    "disabled_iso": None,
                    "activation_timestamp": None,
                    "activation_iso": None,
                    "authorized_phases": phases,
                    "teacher_label": teacher_label or "Teacher",
                    "session_token_hash": None,
                    "teacher_id": None,
                }
                self._save()
                return code
        raise RuntimeError("Unable to allocate a unique invitation code.")

    def verify_and_register_teacher(self, invite_code):
        self._sync_external()
        code = str(invite_code or "").strip().upper()
        record = self.invite_db.get(code)
        if record is None:
            return {"ok": False, "reason": "INVALID_INVITE_CODE", "rbac": None, "session_token": None}
        if not record.get("is_enabled", True):
            return {"ok": False, "reason": "INVITE_DISABLED", "rbac": None, "session_token": None}
        if record.get("is_activated"):
            return {"ok": False, "reason": "INVITE_ALREADY_ACTIVATED", "rbac": None, "session_token": None}

        teacher_id = "T-" + uuid.uuid4().hex
        session_token = uuid.uuid4().hex + uuid.uuid4().hex
        token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
        phases = _normalize_phase_list(record["authorized_phases"])
        is_admin = phases == list(VALID_PHASES)
        rbac = {
            "role": "PRINCIPAL_ADMIN" if is_admin else "INSTRUCTOR",
            "teacher_id": teacher_id,
            "authorized_phases": phases,
            "permissions": {
                "view_phases": list(VALID_PHASES),
                "edit_phases": phases,
                "grade_phases": phases,
                "manage_students": is_admin,
                "manage_teachers": is_admin,
                "manage_weight_scales": is_admin,
            },
        }
        record.update({
            "is_activated": True,
            "activation_timestamp": unix_now(),
            "activation_iso": datetime.now(timezone.utc).isoformat(),
            "session_token_hash": token_hash,
            "teacher_id": teacher_id,
        })
        self.session_db[token_hash] = {
            "teacher_id": teacher_id,
            "created_timestamp": unix_now(),
            "created_iso": datetime.now(timezone.utc).isoformat(),
            "rbac": rbac,
            "active": True,
        }
        self._save()
        return {"ok": True, "reason": None, "session_token": session_token, "rbac": rbac}

    def set_invite_enabled(self, invite_code, enabled):
        self._sync_external()
        code = str(invite_code or "").strip().upper()
        record = self.invite_db.get(code)
        if record is None:
            raise KeyError("Invite code not found.")
        record["is_enabled"] = bool(enabled)
        if enabled:
            record["disabled_timestamp"] = None
            record["disabled_iso"] = None
        else:
            record["disabled_timestamp"] = unix_now()
            record["disabled_iso"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return dict(record)

    def reissue_invite(self, invite_code):
        self._sync_external()
        code = str(invite_code or "").strip().upper()
        record = self.invite_db.get(code)
        if record is None:
            raise KeyError("Invite code not found.")
        if not record.get("is_activated"):
            record["is_enabled"] = False
            record["disabled_timestamp"] = unix_now()
            record["disabled_iso"] = datetime.now(timezone.utc).isoformat()
        new_code = self.generate_invite_code(
            record.get("authorized_phases") or [7],
            record.get("teacher_label") or "Teacher",
        )
        self.invite_db[new_code]["reissued_from"] = code
        self._save()
        return new_code

    def validate_session(self, session_token):
        token_hash = hashlib.sha256(str(session_token or "").encode("utf-8")).hexdigest()
        session = self.session_db.get(token_hash)
        if not session or not session.get("active"):
            return None
        return dict(session)

    def revoke_session(self, session_token):
        token_hash = hashlib.sha256(str(session_token or "").encode("utf-8")).hexdigest()
        session = self.session_db.get(token_hash)
        if not session:
            return False
        session["active"] = False
        session["revoked_timestamp"] = unix_now()
        session["revoked_iso"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return True


class AuthenticationManager:
    """Local account registry for administrators, teachers, and students.

    Passwords are never stored in plaintext. Each account uses its own random salt
    and PBKDF2-HMAC-SHA256 digest. Teacher registration is bound to the existing
    one-time invite-code workflow, while the first administrator can bootstrap the
    installation only when no administrator account exists.
    """

    PBKDF2_ITERATIONS = 310000

    def __init__(self, store, model):
        self.store = store
        self.model = model
        self.accounts = store.data.setdefault("accounts", {})
        self.audit_log = store.data.setdefault("auth_audit", [])
        self.security_meta = store.data.setdefault("auth_security", {})
        self.teacher_manager = TeacherOnboardingManager(store)
        for account in self.accounts.values():
            account.setdefault("must_change_password", False)
            account.setdefault("recovery_code", None)
            account.setdefault("recovery_code_created_at", None)
            account.setdefault("recovery_failed_attempts", 0)
            account.setdefault("recovery_locked_until", 0)
            account.setdefault("security_question", None)
            account.setdefault("security_answer", None)
            account.setdefault("security_answer_failed_attempts", 0)
            account.setdefault("security_answer_locked_until", 0)
        self._pending_recovery_codes = {}
        self._ensure_system_admin()
        for invite in self.teacher_manager.invite_db.values():
            invite.setdefault("is_enabled", True)
            invite.setdefault("disabled_timestamp", None)
            invite.setdefault("disabled_iso", None)

    def _sync_external(self):
        return self.store.reload_if_changed()

    def _ensure_system_admin(self):
        """Create or normalize the requested built-in admin exactly once.

        This migration is idempotent. On the first run of this build it guarantees
        that username ``admin`` exists with administrator privileges, the requested
        initial password hash, and the configured security question/answer hash.
        After the migration flag is stored, later password changes are never
        overwritten on application restart.
        """
        if self.security_meta.get("system_admin_seed_v1_applied"):
            return

        user_id, account = self._find_by_username(SYSTEM_ADMIN_USERNAME)
        if account is None:
            user_id = "U-" + uuid.uuid4().hex
            account = {
                "user_id": user_id,
                "username": SYSTEM_ADMIN_USERNAME,
                "display_name": SYSTEM_ADMIN_DISPLAY_NAME,
                "role": "ADMIN",
                "password": dict(SYSTEM_ADMIN_PASSWORD_HASH),
                "active": True,
                "created_at": now_iso(),
                "created_timestamp": unix_now(),
                "last_login_at": None,
                "last_login_timestamp": None,
                "failed_login_count": 0,
                "student_id": None,
                "teacher_id": None,
                "authorized_phases": list(VALID_PHASES),
                "must_change_password": False,
                "recovery_code": None,
                "recovery_code_created_at": None,
                "recovery_failed_attempts": 0,
                "recovery_locked_until": 0,
                "security_question": SYSTEM_ADMIN_SECURITY_QUESTION,
                "security_answer": dict(SYSTEM_ADMIN_SECURITY_ANSWER_HASH),
                "security_answer_failed_attempts": 0,
                "security_answer_locked_until": 0,
                "system_seeded": True,
            }
            # Keep the legacy recovery-code path available without exposing an
            # additional plaintext secret during system bootstrap.
            hidden_recovery = self._generate_recovery_code()
            account["recovery_code"] = self._hash_recovery_code(hidden_recovery)
            account["recovery_code_created_at"] = now_iso()
            self.accounts[user_id] = account
            action = "SYSTEM_ADMIN_CREATED"
        else:
            # Apply the requested credentials exactly once even if a previous build
            # already had a user called admin. This deliberately does not repeat on
            # later launches, so a subsequent password change remains authoritative.
            account.update({
                "username": SYSTEM_ADMIN_USERNAME,
                "display_name": account.get("display_name") or SYSTEM_ADMIN_DISPLAY_NAME,
                "role": "ADMIN",
                "password": dict(SYSTEM_ADMIN_PASSWORD_HASH),
                "active": True,
                "student_id": None,
                "teacher_id": None,
                "authorized_phases": list(VALID_PHASES),
                "must_change_password": False,
                "security_question": SYSTEM_ADMIN_SECURITY_QUESTION,
                "security_answer": dict(SYSTEM_ADMIN_SECURITY_ANSWER_HASH),
                "security_answer_failed_attempts": 0,
                "security_answer_locked_until": 0,
                "system_seeded": True,
            })
            if not isinstance(account.get("recovery_code"), dict):
                hidden_recovery = self._generate_recovery_code()
                account["recovery_code"] = self._hash_recovery_code(hidden_recovery)
                account["recovery_code_created_at"] = now_iso()
            action = "SYSTEM_ADMIN_NORMALIZED"

        self.security_meta["system_admin_seed_v1_applied"] = True
        self.security_meta["system_admin_username"] = SYSTEM_ADMIN_USERNAME
        self.security_meta["system_admin_seeded_at"] = now_iso()
        self._audit(user_id, action, {"username": SYSTEM_ADMIN_USERNAME})
        self.store.save()

    @staticmethod
    def normalize_username(username):
        value = str(username or "").strip().casefold()
        if not (3 <= len(value) <= 32):
            raise ValueError("Username must contain 3–32 characters.")
        if any(not (ch.isalnum() or ch in "._-") for ch in value):
            raise ValueError("Username may contain letters, numbers, dot, underscore, and hyphen only.")
        return value

    @staticmethod
    def _validate_password(password):
        value = str(password or "")
        if len(value) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        if len(value) > 256:
            raise ValueError("Password is too long.")
        return value

    @classmethod
    def _hash_password(cls, password, salt_hex=None, iterations=None):
        password = cls._validate_password(password)
        iterations = int(iterations or cls.PBKDF2_ITERATIONS)
        salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return {
            "salt": salt.hex(),
            "digest": digest.hex(),
            "iterations": iterations,
            "algorithm": "pbkdf2_hmac_sha256",
        }

    @classmethod
    def _verify_password(cls, password, password_record):
        if not isinstance(password_record, dict):
            return False
        try:
            candidate = cls._hash_password(
                password,
                salt_hex=password_record["salt"],
                iterations=int(password_record.get("iterations", cls.PBKDF2_ITERATIONS)),
            )["digest"]
        except Exception:
            return False
        return hmac.compare_digest(candidate, str(password_record.get("digest", "")))

    @staticmethod
    def _normalize_recovery_code(code):
        raw = str(code or "").strip().upper()
        if raw.startswith("ACA-REC-"):
            raw = raw[len("ACA-REC-"):]
        raw = "".join(ch for ch in raw if ch.isalnum())
        return raw

    @classmethod
    def _hash_recovery_code(cls, code, salt_hex=None, iterations=None):
        normalized = cls._normalize_recovery_code(code)
        if len(normalized) != 8:
            raise ValueError("Recovery code must contain 8 code characters.")
        iterations = int(iterations or cls.PBKDF2_ITERATIONS)
        salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", normalized.encode("ascii"), salt, iterations)
        return {
            "salt": salt.hex(),
            "digest": digest.hex(),
            "iterations": iterations,
            "algorithm": "pbkdf2_hmac_sha256",
        }

    @classmethod
    def _verify_recovery_code(cls, code, record):
        if not isinstance(record, dict):
            return False
        try:
            candidate = cls._hash_recovery_code(
                code,
                salt_hex=record["salt"],
                iterations=int(record.get("iterations", cls.PBKDF2_ITERATIONS)),
            )["digest"]
        except Exception:
            return False
        return hmac.compare_digest(candidate, str(record.get("digest", "")))

    @staticmethod
    def _normalize_security_answer(answer):
        value = str(answer or "").strip().casefold()
        if not value or len(value) > 256:
            raise ValueError("Security answer is invalid.")
        return value

    @classmethod
    def _hash_security_answer(cls, answer, salt_hex=None, iterations=None):
        normalized = cls._normalize_security_answer(answer)
        iterations = int(iterations or cls.PBKDF2_ITERATIONS)
        salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", normalized.encode("utf-8"), salt, iterations)
        return {
            "salt": salt.hex(),
            "digest": digest.hex(),
            "iterations": iterations,
            "algorithm": "pbkdf2_hmac_sha256",
        }

    @classmethod
    def _verify_security_answer(cls, answer, record):
        if not isinstance(record, dict):
            return False
        try:
            candidate = cls._hash_security_answer(
                answer,
                salt_hex=record["salt"],
                iterations=int(record.get("iterations", cls.PBKDF2_ITERATIONS)),
            )["digest"]
        except Exception:
            return False
        return hmac.compare_digest(candidate, str(record.get("digest", "")))

    def get_security_question(self, username):
        try:
            normalized = self.normalize_username(username)
        except Exception:
            return None
        _user_id, account = self._find_by_username(normalized)
        if not account or not account.get("active", True):
            return None
        question = str(account.get("security_question") or "").strip()
        return question or None

    def recover_password_with_security_answer(self, username, answer, new_password):
        self._sync_external()
        try:
            normalized = self.normalize_username(username)
        except Exception:
            normalized = str(username or "").strip().casefold()
        user_id, account = self._find_by_username(normalized) if normalized else (None, None)
        now_ts = unix_now()
        generic = "Recovery failed. Check the username and security answer, or try again later."
        if account is None or not account.get("active", True):
            raise ValueError(generic)
        if not account.get("security_question") or not isinstance(account.get("security_answer"), dict):
            raise ValueError(generic)
        locked_until = int(account.get("security_answer_locked_until", 0) or 0)
        if locked_until > now_ts:
            raise ValueError(generic)
        if not self._verify_security_answer(answer, account.get("security_answer")):
            attempts = int(account.get("security_answer_failed_attempts", 0)) + 1
            account["security_answer_failed_attempts"] = attempts
            if attempts >= 5:
                account["security_answer_locked_until"] = now_ts + 15 * 60
                account["security_answer_failed_attempts"] = 0
            self._audit(user_id, "SECURITY_QUESTION_RECOVERY_FAILED", {})
            self.store.save()
            raise ValueError(generic)

        account["password"] = self._hash_password(new_password)
        account["must_change_password"] = False
        account["failed_login_count"] = 0
        account["security_answer_failed_attempts"] = 0
        account["security_answer_locked_until"] = 0
        account["password_changed_at"] = now_iso()
        new_code = self._issue_recovery_code(account, audit_action="RECOVERY_CODE_ROTATED_AFTER_SECURITY_QUESTION")
        self._pending_recovery_codes.pop(user_id, None)
        self._audit(user_id, "PASSWORD_RECOVERED_WITH_SECURITY_QUESTION", {})
        self.store.save()
        return {
            "user_id": user_id,
            "username": account.get("username"),
            "recovery_code_once": new_code,
        }

    @staticmethod
    def _generate_recovery_code():
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        body = "".join(secrets.choice(alphabet) for _ in range(8))
        return f"ACA-REC-{body[:4]}-{body[4:]}"

    def _issue_recovery_code(self, account, *, audit_action="RECOVERY_CODE_ISSUED"):
        code = self._generate_recovery_code()
        account["recovery_code"] = self._hash_recovery_code(code)
        account["recovery_code_created_at"] = now_iso()
        account["recovery_failed_attempts"] = 0
        account["recovery_locked_until"] = 0
        user_id = account.get("user_id")
        if user_id:
            self._pending_recovery_codes[user_id] = code
            self._audit(user_id, audit_action, {})
        return code

    def ensure_recovery_code(self, user_id):
        account = self.accounts.get(user_id)
        if not account:
            raise KeyError("Account not found.")
        if isinstance(account.get("recovery_code"), dict):
            return None
        code = self._issue_recovery_code(account, audit_action="RECOVERY_CODE_INITIALIZED")
        self._pending_recovery_codes.pop(user_id, None)
        self.store.save()
        return code

    def take_pending_recovery_code(self, user_id):
        return self._pending_recovery_codes.pop(user_id, None)

    def regenerate_recovery_code(self, user_id, current_password):
        self._sync_external()
        account = self.accounts.get(user_id)
        if not account or not account.get("active", True):
            raise KeyError("Account not found or disabled.")
        if not self._verify_password(current_password, account.get("password")):
            raise ValueError("Current password is incorrect.")
        code = self._issue_recovery_code(account, audit_action="RECOVERY_CODE_REGENERATED")
        self._pending_recovery_codes.pop(user_id, None)
        self.store.save()
        return code

    def recover_password(self, username, recovery_code, new_password):
        self._sync_external()
        # Use a generic error so the recovery flow does not disclose whether a
        # username exists. Successful use is one-time: a fresh code is issued.
        try:
            normalized = self.normalize_username(username)
        except Exception:
            normalized = str(username or "").strip().casefold()
        user_id, account = self._find_by_username(normalized) if normalized else (None, None)
        now_ts = unix_now()
        generic = "Recovery failed. Check the username and recovery code, or try again later."
        if account is None or not account.get("active", True):
            raise ValueError(generic)
        locked_until = int(account.get("recovery_locked_until", 0) or 0)
        if locked_until > now_ts:
            raise ValueError(generic)
        if not self._verify_recovery_code(recovery_code, account.get("recovery_code")):
            attempts = int(account.get("recovery_failed_attempts", 0)) + 1
            account["recovery_failed_attempts"] = attempts
            if attempts >= 5:
                account["recovery_locked_until"] = now_ts + 15 * 60
                account["recovery_failed_attempts"] = 0
            self._audit(user_id, "PASSWORD_RECOVERY_FAILED", {})
            self.store.save()
            raise ValueError(generic)
        account["password"] = self._hash_password(new_password)
        account["must_change_password"] = False
        account["failed_login_count"] = 0
        account["password_changed_at"] = now_iso()
        new_code = self._issue_recovery_code(account, audit_action="RECOVERY_CODE_ROTATED_AFTER_RECOVERY")
        self._pending_recovery_codes.pop(user_id, None)
        self._audit(user_id, "PASSWORD_RECOVERED_WITH_CODE", {})
        self.store.save()
        return {"user_id": user_id, "username": account.get("username"), "recovery_code_once": new_code}

    def _find_by_username(self, username):
        normalized = str(username or "").strip().casefold()
        for user_id, account in self.accounts.items():
            if str(account.get("username", "")).casefold() == normalized:
                return user_id, account
        return None, None

    def username_available(self, username):
        _, account = self._find_by_username(username)
        return account is None

    def has_admin(self):
        return any(a.get("role") == "ADMIN" and a.get("active", True) for a in self.accounts.values())

    def _base_account(self, username, password, display_name, role):
        normalized = self.normalize_username(username)
        if not self.username_available(normalized):
            raise ValueError("This username is already registered.")
        display = str(display_name or "").strip()
        if not display:
            raise ValueError("Display name is required.")
        account = {
            "user_id": "U-" + uuid.uuid4().hex,
            "username": normalized,
            "display_name": display,
            "role": role,
            "password": self._hash_password(password),
            "active": True,
            "created_at": now_iso(),
            "created_timestamp": unix_now(),
            "last_login_at": None,
            "last_login_timestamp": None,
            "failed_login_count": 0,
            "student_id": None,
            "teacher_id": None,
            "authorized_phases": [],
            "recovery_code": None,
            "recovery_code_created_at": None,
            "recovery_failed_attempts": 0,
            "recovery_locked_until": 0,
            "security_question": None,
            "security_answer": None,
            "security_answer_failed_attempts": 0,
            "security_answer_locked_until": 0,
        }
        self._issue_recovery_code(account, audit_action="RECOVERY_CODE_CREATED_WITH_ACCOUNT")
        return account

    def register_admin(self, username, password, display_name, *, bootstrap=False):
        # Administrator creation is never part of normal self-registration.
        # It is available only through the explicit one-time Principal Setup flow.
        if bootstrap is not True:
            raise PermissionError("Administrator accounts can only be created through Principal Setup.")
        if self.has_admin():
            raise PermissionError("Administrator registration is already closed for this installation.")
        account = self._base_account(username, password, display_name, "ADMIN")
        account["authorized_phases"] = list(VALID_PHASES)
        account["bootstrap_created"] = True
        self.accounts[account["user_id"]] = account
        self._audit(account["user_id"], "ADMIN_REGISTERED", {"username": account["username"], "bootstrap": True})
        self.store.save()
        public = self._public_account(account)
        public["recovery_code_once"] = self.take_pending_recovery_code(account["user_id"])
        return public

    def register_student(self, username, password, display_name, age=0, skill_class="Unranked"):
        self._sync_external()
        account = self._base_account(username, password, display_name, "STUDENT")
        try:
            age_value = int(age or 0)
        except (TypeError, ValueError):
            raise ValueError("Age must be a whole number.")
        if age_value < 0 or age_value > 120:
            raise ValueError("Age is outside the supported range.")
        sid = self.model.add_student(display_name, age_value, str(skill_class or "Unranked"), ["Gameplay", "Decoration"])
        account["student_id"] = sid
        self.accounts[account["user_id"]] = account
        self._audit(account["user_id"], "STUDENT_REGISTERED", {"student_id": sid, "username": account["username"]})
        self.store.save()
        public = self._public_account(account)
        public["recovery_code_once"] = self.take_pending_recovery_code(account["user_id"])
        return public

    def register_teacher(self, invite_code, username, password, display_name):
        self._sync_external()
        normalized = self.normalize_username(username)
        account = self._base_account(normalized, password, display_name, "TEACHER")
        result = self.teacher_manager.verify_and_register_teacher(invite_code)
        if not result.get("ok"):
            reason = result.get("reason") or "INVITE_REJECTED"
            if reason == "INVALID_INVITE_CODE":
                raise ValueError("Invite code is invalid.")
            if reason == "INVITE_ALREADY_ACTIVATED":
                raise ValueError("Invite code has already been used.")
            if reason == "INVITE_DISABLED":
                raise ValueError("Invite code has been disabled by an administrator.")
            raise ValueError(f"Invite code rejected: {reason}")
        rbac = result["rbac"]
        account["teacher_id"] = rbac.get("teacher_id")
        account["authorized_phases"] = list(rbac.get("authorized_phases", []))
        account["invite_code"] = str(invite_code).strip().upper()
        self.accounts[account["user_id"]] = account
        self._audit(account["user_id"], "TEACHER_REGISTERED", {
            "teacher_id": account["teacher_id"],
            "authorized_phases": account["authorized_phases"],
        })
        self.store.save()
        public = self._public_account(account)
        public["recovery_code_once"] = self.take_pending_recovery_code(account["user_id"])
        return public

    def login(self, username, password):
        self._sync_external()
        try:
            normalized = self.normalize_username(username)
        except ValueError:
            normalized = str(username or "").strip().casefold()
        user_id, account = self._find_by_username(normalized) if normalized else (None, None)
        if account is None or not account.get("active", True):
            self._audit(None, "LOGIN_FAILED", {"username": normalized, "reason": "UNKNOWN_OR_DISABLED"})
            self.store.save()
            raise ValueError("Invalid username or password.")
        if not self._verify_password(password, account.get("password")):
            account["failed_login_count"] = int(account.get("failed_login_count", 0)) + 1
            self._audit(user_id, "LOGIN_FAILED", {"username": normalized, "reason": "BAD_PASSWORD"})
            self.store.save()
            raise ValueError("Invalid username or password.")
        account["failed_login_count"] = 0
        account["last_login_at"] = now_iso()
        account["last_login_timestamp"] = unix_now()
        recovery_code_once = self.ensure_recovery_code(user_id)
        self._audit(user_id, "LOGIN_SUCCESS", {"username": normalized, "role": account.get("role")})
        self.store.save()
        context = self.session_context(account)
        if recovery_code_once:
            context["recovery_code_once"] = recovery_code_once
        return context

    def session_context(self, account):
        role = account.get("role", "STUDENT")
        phases = list(account.get("authorized_phases", []))
        is_admin = role == "ADMIN"
        is_teacher = role == "TEACHER"
        student_id = account.get("student_id")
        return {
            "user_id": account.get("user_id"),
            "username": account.get("username"),
            "display_name": account.get("display_name"),
            "role": role,
            "student_id": student_id,
            "teacher_id": account.get("teacher_id"),
            "must_change_password": bool(account.get("must_change_password", False)),
            "authorized_phases": list(VALID_PHASES) if is_admin else phases,
            "permissions": {
                "view_all_students": is_admin or is_teacher,
                "manage_students": is_admin,
                "manage_teachers": is_admin,
                "manage_accounts": is_admin,
                "backup_database": is_admin,
                "grade_phases": list(VALID_PHASES) if is_admin else phases if is_teacher else [],
                "edit_own_submission_links": role == "STUDENT",
                "manage_graduation": is_admin or (is_teacher and 7 in phases),
            },
        }

    def account_context(self, user_id):
        account = self.accounts.get(user_id)
        if not account or not account.get("active", True):
            return None
        return self.session_context(account)

    def list_accounts(self):
        return [self._public_account(account) for account in self.accounts.values()]

    def _require_admin_actor(self, actor_context):
        if not actor_context or actor_context.get("role") != "ADMIN":
            raise PermissionError("Only an administrator can perform this operation.")

    def _active_admin_count(self):
        return sum(
            1 for account in self.accounts.values()
            if account.get("role") == "ADMIN" and account.get("active", True)
        )

    def set_account_active(self, user_id, active, actor_context):
        self._sync_external()
        self._require_admin_actor(actor_context)
        account = self.accounts.get(user_id)
        if not account:
            raise KeyError("Account not found.")
        if not active and account.get("role") == "ADMIN":
            if account.get("user_id") == actor_context.get("user_id"):
                raise ValueError("You cannot disable the administrator account currently in use.")
            if account.get("active", True) and self._active_admin_count() <= 1:
                raise ValueError("The last active administrator cannot be disabled.")
        account["active"] = bool(active)
        self._audit(user_id, "ACCOUNT_ENABLED" if active else "ACCOUNT_DISABLED", {"by": actor_context.get("user_id")})
        self.store.save()
        return self._public_account(account)

    def change_account_role(self, user_id, new_role, actor_context, authorized_phases=None):
        self._sync_external()
        self._require_admin_actor(actor_context)
        account = self.accounts.get(user_id)
        if not account:
            raise KeyError("Account not found.")
        if account.get("user_id") == actor_context.get("user_id"):
            raise ValueError("Change your own administrator role from another administrator account.")

        role = str(new_role or "").strip().upper()
        if role not in ("ADMIN", "TEACHER", "STUDENT"):
            raise ValueError("Role must be ADMIN, TEACHER, or STUDENT.")

        old_role = account.get("role", "STUDENT")
        if old_role == "ADMIN" and role != "ADMIN" and account.get("active", True) and self._active_admin_count() <= 1:
            raise ValueError("The last active administrator cannot be demoted.")

        if role == "ADMIN":
            account["authorized_phases"] = list(VALID_PHASES)
        elif role == "TEACHER":
            phases = _normalize_phase_list(authorized_phases or account.get("authorized_phases") or [7])
            account["authorized_phases"] = phases
            if not account.get("teacher_id"):
                account["teacher_id"] = "T-" + uuid.uuid4().hex
        else:
            account["authorized_phases"] = []
            if not account.get("student_id") or account.get("student_id") not in self.model.students:
                sid = self.model.add_student(
                    account.get("display_name") or account.get("username") or "Student",
                    0,
                    "Unranked",
                    ["Gameplay", "Decoration"],
                )
                account["student_id"] = sid

        account["role"] = role
        account["role_changed_at"] = now_iso()
        self._audit(user_id, "ACCOUNT_ROLE_CHANGED", {
            "by": actor_context.get("user_id"),
            "from": old_role,
            "to": role,
            "authorized_phases": list(account.get("authorized_phases", [])),
        })
        self.store.save()
        return self._public_account(account)

    def admin_reset_password(self, user_id, temporary_password, actor_context, force_change=True):
        self._sync_external()
        self._require_admin_actor(actor_context)
        account = self.accounts.get(user_id)
        if not account:
            raise KeyError("Account not found.")
        account["password"] = self._hash_password(temporary_password)
        # Administrator-forced resets invalidate the user's previous recovery secret.
        # A fresh one is issued only after the user completes the forced password change.
        account["recovery_code"] = None
        account["recovery_code_created_at"] = None
        account["recovery_failed_attempts"] = 0
        account["recovery_locked_until"] = 0
        account["must_change_password"] = bool(force_change)
        account["password_reset_at"] = now_iso()
        account["failed_login_count"] = 0
        self._audit(user_id, "PASSWORD_RESET_BY_ADMIN", {
            "by": actor_context.get("user_id"),
            "force_change": bool(force_change),
        })
        self.store.save()
        return self._public_account(account)

    def complete_forced_password_change(self, user_id, current_password, new_password):
        account = self.accounts.get(user_id)
        if not account or not account.get("active", True):
            raise KeyError("Account not found or disabled.")
        if not account.get("must_change_password", False):
            raise ValueError("This account does not require a forced password change.")
        if not self._verify_password(current_password, account.get("password")):
            raise ValueError("Temporary password is incorrect.")
        account["password"] = self._hash_password(new_password)
        account["must_change_password"] = False
        account["password_changed_at"] = now_iso()
        recovery_code = self._issue_recovery_code(account, audit_action="RECOVERY_CODE_ROTATED_AFTER_FORCED_CHANGE")
        self._pending_recovery_codes.pop(user_id, None)
        self._audit(user_id, "FORCED_PASSWORD_CHANGE_COMPLETED", {})
        self.store.save()
        return {"account": self._public_account(account), "recovery_code_once": recovery_code}

    def change_password(self, user_id, current_password, new_password):
        self._sync_external()
        account = self.accounts.get(user_id)
        if not account or not account.get("active", True):
            raise KeyError("Account not found or disabled.")
        if not self._verify_password(current_password, account.get("password")):
            raise ValueError("Current password is incorrect.")
        if self._verify_password(new_password, account.get("password")):
            raise ValueError("New password must be different from the current password.")
        account["password"] = self._hash_password(new_password)
        account["must_change_password"] = False
        account["password_changed_at"] = now_iso()
        recovery_code = self._issue_recovery_code(account, audit_action="RECOVERY_CODE_ROTATED_AFTER_PASSWORD_CHANGE")
        self._pending_recovery_codes.pop(user_id, None)
        self._audit(user_id, "PASSWORD_CHANGED", {})
        self.store.save()
        return {"account": self._public_account(account), "recovery_code_once": recovery_code}

    @staticmethod
    def _public_account(account):
        return {
            "user_id": account.get("user_id"),
            "username": account.get("username"),
            "display_name": account.get("display_name"),
            "role": account.get("role"),
            "active": bool(account.get("active", True)),
            "student_id": account.get("student_id"),
            "teacher_id": account.get("teacher_id"),
            "authorized_phases": list(account.get("authorized_phases", [])),
            "must_change_password": bool(account.get("must_change_password", False)),
            "created_at": account.get("created_at"),
            "last_login_at": account.get("last_login_at"),
            "recovery_code_configured": isinstance(account.get("recovery_code"), dict),
            "security_question": account.get("security_question"),
            "security_question_configured": bool(account.get("security_question") and isinstance(account.get("security_answer"), dict)),
        }

    def _audit(self, user_id, action, payload):
        self.audit_log.append({
            "event_id": uuid.uuid4().hex,
            "user_id": user_id,
            "action": action,
            "payload": payload or {},
            "created_at": now_iso(),
            "unix_timestamp": unix_now(),
        })


class ACAApiError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class ACAApiClient:
    """Small stdlib HTTP client used by the packaged desktop app.

    requests is intentionally not required, which keeps PyInstaller bundles small.
    TLS certificate verification stays enabled through urllib's default HTTPS stack.
    """
    def __init__(self, base_url, timeout=12.0):
        self.base_url = str(base_url or "").rstrip("/")
        self.timeout = float(timeout)
        self.token = None

        # Use an explicit CA bundle when certifi is available. This avoids
        # CERTIFICATE_VERIFY_FAILED on macOS Python installations whose local
        # OpenSSL trust store is incomplete, while keeping certificate
        # verification fully enabled.
        if certifi is not None:
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            self.ssl_context = ssl.create_default_context()

    def request(self, method, path, payload=None, query=None, auth=True):
        """HTTP request with bounded retry for sleeping/cloud-hosted ACA servers.

        Railway Serverless can cold-start on the first request and may briefly
        return 502/503. Retry only transient transport/server failures; never
        retry auth, validation, permission, or conflict responses.
        """
        if not self.base_url:
            raise ACAApiError("ACA server URL is not configured.")
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth and self.token:
            headers["Authorization"] = "Bearer " + self.token

        transient_statuses = {502, 503, 504}
        delays = (0.0, 0.8, 1.8, 3.5)
        last_error = None

        for attempt, delay in enumerate(delays):
            if delay:
                time.sleep(delay)
            req = urllib.request.Request(url, data=data, headers=headers, method=str(method).upper())
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as response:
                    raw = response.read()
                    if not raw:
                        return {}
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = None
                try:
                    body = json.loads(exc.read().decode("utf-8"))
                    detail = body.get("detail") if isinstance(body, dict) else None
                except Exception:
                    detail = None
                last_error = ACAApiError(detail or f"ACA server returned HTTP {exc.code}.", status=exc.code)
                if exc.code not in transient_statuses or attempt == len(delays) - 1:
                    raise last_error from None
            except (urllib.error.URLError, TimeoutError) as exc:
                reason = getattr(exc, "reason", exc)
                last_error = ACAApiError(f"Cannot connect to ACA server: {reason}")
                if attempt == len(delays) - 1:
                    raise last_error from None
            except json.JSONDecodeError:
                raise ACAApiError("ACA server returned an invalid response.") from None

        raise last_error or ACAApiError("Cannot connect to ACA server.")



def _remote_json_diff(old, new, path=None):
    """Build path-level optimistic patch operations.

    Dicts are diffed recursively; lists are atomic so grade transaction order is
    preserved and concurrent changes to the same lesson become explicit conflicts.
    """
    path = list(path or [])
    ops = []
    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old) | set(new)
        for key in sorted(keys):
            child = path + [str(key)]
            if key not in old:
                if isinstance(new[key], dict):
                    # Recurse into newly-created dicts so server-side RBAC can inspect
                    # individual lesson fields rather than accepting a whole object.
                    ops.extend(_remote_json_diff({}, new[key], child))
                else:
                    ops.append({"path": child, "old_exists": False, "delete": False, "value": copy.deepcopy(new[key])})
            elif key not in new:
                ops.append({"path": child, "old_exists": True, "old": copy.deepcopy(old[key]), "delete": True})
            else:
                ops.extend(_remote_json_diff(old[key], new[key], child))
        return ops
    if old != new:
        ops.append({"path": path, "old_exists": True, "old": copy.deepcopy(old), "delete": False, "value": copy.deepcopy(new)})
    return ops


class ServerDataStore(DataStore):
    """Server-backed replacement for DataStore with the same surface API."""
    poll_interval_ms = 1000

    def __init__(self, server_url):
        self.server_url = str(server_url).rstrip("/")
        self.api = ACAApiClient(self.server_url)
        self.path = f"server://{self.server_url}"
        self.data = self._default_data()
        self.data.setdefault("auth_security", {})
        self._last_file_signature = None
        self.revision = 0
        self._base_snapshot = copy.deepcopy(self.data)
        self._load_local_preferences()

    def _load_local_preferences(self):
        try:
            pref_path = CLIENT_PREFS_FILE
            with open(pref_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
            language = str((prefs or {}).get("language") or "").strip().lower()
            if language in ("ru", "en"):
                self.data.setdefault("settings", {})["language"] = language
        except Exception:
            pass

    def _save_local_preferences(self):
        try:
            pref_path = CLIENT_PREFS_FILE
            tmp = pref_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"language": self.data.get("settings", {}).get("language", "ru")}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, pref_path)
        except OSError:
            pass

    def set_token(self, token):
        self.api.token = token or None

    def apply_bundle(self, bundle):
        incoming = bundle.get("state") if isinstance(bundle, dict) else None
        if not isinstance(incoming, dict):
            return False
        current = self.data
        temp = incoming
        original = self.data
        try:
            self.data = temp
            self._migrate(persist=False)
            temp = self.data
        finally:
            self.data = original
        self._sync_in_place(current, temp)
        self.revision = int(bundle.get("revision") or self.revision or 0)
        self._base_snapshot = copy.deepcopy(current)
        self._save_local_preferences()
        return True

    def save(self):
        self._save_local_preferences()
        if not self.api.token:
            # Login/registration screen can persist presentation preferences before
            # a server session exists. Domain data is never written locally.
            self._base_snapshot = copy.deepcopy(self.data)
            return
        ops = _remote_json_diff(self._base_snapshot, self.data)
        if not ops:
            return
        try:
            bundle = self.api.request(
                "POST", "/api/v1/state/patch",
                {"base_revision": self.revision, "ops": ops},
            )
        except ACAApiError as exc:
            if exc.status == 409:
                try:
                    self.force_reload()
                except Exception:
                    pass
            raise
        self.apply_bundle(bundle)

    def reload_if_changed(self):
        if not self.api.token:
            return False
        bundle = self.api.request("GET", "/api/v1/state", query={"revision": self.revision})
        if not bundle.get("changed", False):
            return False
        return self.apply_bundle(bundle)

    def force_reload(self):
        if not self.api.token:
            return False
        bundle = self.api.request("GET", "/api/v1/state")
        return self.apply_bundle(bundle)

    def backup(self):
        if not self.api.token:
            raise ACAApiError("Sign in before creating a server backup.")
        result = self.api.request("POST", "/api/v1/admin/backup", {})
        return result.get("path") or "server backup"


class ServerTeacherOnboardingManager:
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        self.store = auth_manager.store
        self.invite_db = self.store.data.setdefault("teacher_invites", {})
        self.session_db = self.store.data.setdefault("teacher_sessions", {})

    def _apply(self, bundle):
        self.auth_manager._apply_authenticated_bundle(bundle)
        self.invite_db = self.store.data.setdefault("teacher_invites", {})
        self.session_db = self.store.data.setdefault("teacher_sessions", {})

    def generate_invite_code(self, authorized_phases, teacher_label=None):
        bundle = self.store.api.request("POST", "/api/v1/admin/invites", {
            "authorized_phases": list(authorized_phases or []),
            "teacher_label": teacher_label or "Teacher",
        })
        self._apply(bundle)
        return bundle.get("code")

    def set_invite_enabled(self, invite_code, enabled):
        code = urllib.parse.quote(str(invite_code or ""), safe="")
        bundle = self.store.api.request("POST", f"/api/v1/admin/invites/{code}/enabled", {"enabled": bool(enabled)})
        self._apply(bundle)
        return bundle.get("record") or {}

    def reissue_invite(self, invite_code):
        code = urllib.parse.quote(str(invite_code or ""), safe="")
        bundle = self.store.api.request("POST", f"/api/v1/admin/invites/{code}/reissue", {})
        self._apply(bundle)
        return bundle.get("code")


class ServerAuthenticationManager:
    """Authentication facade compatible with AuthenticationManager, backed by ACA Server."""
    def __init__(self, store, model):
        self.store = store
        self.model = model
        self.api = store.api
        self._context = None
        self.last_resume_error = None
        self.teacher_manager = ServerTeacherOnboardingManager(self)

    @property
    def accounts(self):
        return self.store.data.setdefault("accounts", {})

    def _write_session_file(self, token):
        if not token:
            return
        try:
            os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
            tmp = SESSION_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"server_url": self.store.server_url, "token": token},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, SESSION_FILE)
            try:
                os.chmod(SESSION_FILE, 0o600)
            except OSError:
                pass
        except OSError:
            pass

    def _clear_session_file(self):
        for path in {SESSION_FILE, LEGACY_SESSION_FILE}:
            try:
                os.remove(path)
            except OSError:
                pass

    def _saved_session_path(self):
        if os.path.exists(SESSION_FILE):
            return SESSION_FILE
        if LEGACY_SESSION_FILE != SESSION_FILE and os.path.exists(LEGACY_SESSION_FILE):
            return LEGACY_SESSION_FILE
        return SESSION_FILE

    def _apply_authenticated_bundle(self, bundle):
        self.store.apply_bundle(bundle)
        context = bundle.get("context") if isinstance(bundle, dict) else None
        if isinstance(context, dict):
            self._context = dict(context)
        return self._context

    def try_resume_session(self):
        session_path = self._saved_session_path()
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                saved = json.load(f)

            if str(saved.get("server_url") or "").rstrip("/") != self.store.server_url:
                return None

            token = str(saved.get("token") or "").strip()
            if not token:
                return None

            self.store.set_token(token)
            bundle = self.api.request("GET", "/api/v1/auth/session")
            context = self._apply_authenticated_bundle(bundle)

            if context:
                self._write_session_file(token)
                if session_path != SESSION_FILE:
                    try:
                        os.remove(session_path)
                    except OSError:
                        pass
            return context

        except FileNotFoundError:
            self.store.set_token(None)
            self._context = None
            return None
        except ACAApiError as exc:
            self.last_resume_error = str(exc)
            self._context = None
            if exc.status == 401:
                self.store.set_token(None)
                self._clear_session_file()
            else:
                self.store.set_token(None)
            return None
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.last_resume_error = str(exc)
            self.store.set_token(None)
            self._context = None
            return None
        except Exception as exc:
            self.last_resume_error = str(exc)
            self.store.set_token(None)
            self._context = None
            return None

    def logout(self):
        try:
            if self.api.token:
                self.api.request("POST", "/api/v1/auth/logout", {})
        except Exception:
            pass
        self.store.set_token(None)
        self._context = None
        self._clear_session_file()

    def has_admin(self):
        try:
            result = self.api.request("GET", "/api/v1/public/status", auth=False)
            return bool(result.get("has_admin"))
        except Exception:
            # Prefer the sign-in screen when the server is temporarily unavailable;
            # exposing Principal Setup would be misleading and unsafe.
            return True

    def login(self, username, password):
        bundle = self.api.request("POST", "/api/v1/auth/login", {"username": username, "password": password}, auth=False)
        token = str(bundle.get("token") or "")
        if not token:
            raise ACAApiError("ACA server did not return a session token.")
        self.store.set_token(token)
        context = self._apply_authenticated_bundle(bundle) or {}
        self._write_session_file(token)
        recovery = bundle.get("recovery_code_once")
        if recovery:
            context = dict(context)
            context["recovery_code_once"] = recovery
        return context

    def register_student(self, username, password, display_name, age=0, skill_class="Unranked"):
        result = self.api.request("POST", "/api/v1/auth/register/student", {
            "username": username, "password": password, "display_name": display_name,
            "age": age, "skill_class": skill_class,
        }, auth=False)
        return result.get("account") or {}

    def register_teacher(self, invite_code, username, password, display_name):
        result = self.api.request("POST", "/api/v1/auth/register/teacher", {
            "invite_code": invite_code, "username": username, "password": password, "display_name": display_name,
        }, auth=False)
        return result.get("account") or {}

    def register_admin(self, username, password, display_name, *, bootstrap=False):
        result = self.api.request("POST", "/api/v1/auth/register/admin", {
            "username": username, "password": password, "display_name": display_name, "bootstrap": bool(bootstrap),
        }, auth=False)
        return result.get("account") or {}

    def get_security_question(self, username):
        result = self.api.request("GET", "/api/v1/auth/security-question", query={"username": username}, auth=False)
        return result.get("question")

    def recover_password(self, username, recovery_code, new_password):
        return self.api.request("POST", "/api/v1/auth/recover/code", {
            "username": username, "recovery_code": recovery_code, "new_password": new_password,
        }, auth=False)

    def recover_password_with_security_answer(self, username, answer, new_password):
        return self.api.request("POST", "/api/v1/auth/recover/question", {
            "username": username, "answer": answer, "new_password": new_password,
        }, auth=False)

    def account_context(self, user_id):
        if not self.api.token or not self._context or self._context.get("user_id") != user_id:
            return None
        try:
            bundle = self.api.request("GET", "/api/v1/auth/context")
            return self._apply_authenticated_bundle(bundle)
        except ACAApiError as exc:
            if exc.status == 401:
                self.logout()
                return None
            raise

    def list_accounts(self):
        result = self.api.request("GET", "/api/v1/admin/accounts")
        return list(result.get("accounts") or [])

    def set_account_active(self, user_id, active, actor_context):
        uid = urllib.parse.quote(str(user_id), safe="")
        bundle = self.api.request("POST", f"/api/v1/admin/accounts/{uid}/active", {"active": bool(active)})
        self._apply_authenticated_bundle(bundle)
        return bundle.get("account") or {}

    def change_account_role(self, user_id, new_role, actor_context, authorized_phases=None):
        uid = urllib.parse.quote(str(user_id), safe="")
        bundle = self.api.request("POST", f"/api/v1/admin/accounts/{uid}/role", {
            "role": new_role, "authorized_phases": list(authorized_phases or []),
        })
        self._apply_authenticated_bundle(bundle)
        return bundle.get("account") or {}

    def admin_reset_password(self, user_id, temporary_password, actor_context, force_change=True):
        uid = urllib.parse.quote(str(user_id), safe="")
        bundle = self.api.request("POST", f"/api/v1/admin/accounts/{uid}/reset-password", {
            "temporary_password": temporary_password, "force_change": bool(force_change),
        })
        self._apply_authenticated_bundle(bundle)
        return bundle.get("account") or {}

    def complete_forced_password_change(self, user_id, current_password, new_password):
        bundle = self.api.request("POST", "/api/v1/auth/complete-forced-password-change", {
            "current_password": current_password, "new_password": new_password,
        })
        self._apply_authenticated_bundle(bundle)
        return {"account": bundle.get("account") or {}, "recovery_code_once": bundle.get("recovery_code_once")}

    def change_password(self, user_id, current_password, new_password):
        bundle = self.api.request("POST", "/api/v1/auth/change-password", {
            "current_password": current_password, "new_password": new_password,
        })
        self._apply_authenticated_bundle(bundle)
        return {"account": (self.store.data.get("accounts", {}).get(user_id) or {}), "recovery_code_once": bundle.get("recovery_code_once")}

    def regenerate_recovery_code(self, user_id, current_password):
        bundle = self.api.request("POST", "/api/v1/auth/regenerate-recovery-code", {"current_password": current_password})
        self._apply_authenticated_bundle(bundle)
        return bundle.get("recovery_code_once")


class StudentPerformanceAnalytics:
    def __init__(self, model):
        if not isinstance(model, AcademyModel):
            raise TypeError("model must be an AcademyModel instance.")
        self.model = model

    def calculate_consistency_rate(self, student_id):
        student = self.model.get_student(student_id)
        if not student:
            raise KeyError(f"Unknown student: {student_id}")
        submitted = 0
        delinquent = 0
        for lesson in CURRICULUM:
            for entry in self.model.get_grades(student_id, lesson["id"]):
                status = str(entry.get("homework_status", "skipped" if entry.get("homework_skipped") else "not_applicable")).lower()
                if status in ("submitted", "skipped", "delinquent"):
                    submitted += 1
                    if status in ("skipped", "delinquent"):
                        delinquent += 1
        if submitted == 0:
            return 1.0
        return max(0.0, min(1.0, (submitted - delinquent) / float(submitted)))

    def clutch_gpa_simulator(self, student_id, target_gpa=8.90):
        target = _finite_number(target_gpa, "target_gpa")
        if not 0.0 <= target <= 10.0:
            raise ValueError("target_gpa must be between 0 and 10.")
        student = self.model.get_student(student_id)
        if not student:
            raise KeyError(f"Unknown student: {student_id}")
        weighted_sum, total_weight = self.model._weighted_totals(student_id)
        current = weighted_sum / total_weight if total_weight else 0.0
        remaining = [l for l in CURRICULUM if not self.model.get_grades(student_id, l["id"])]
        if total_weight > 0 and current + 1e-12 >= target:
            return {"student_id": student_id, "current_gpa": current, "target_gpa": target,
                    "required_consecutive_tens": 0, "strategic_alert": False, "alert_code": None,
                    "reachable": True, "projected_gpa": current,
                    "remaining_slots": [l["id"] for l in remaining], "simulation_path": []}
        if not remaining:
            return {"student_id": student_id, "current_gpa": current, "target_gpa": target,
                    "required_consecutive_tens": None, "strategic_alert": True,
                    "alert_code": "TARGET_UNREACHABLE_NO_REMAINING_SLOTS", "reachable": False,
                    "projected_gpa": current, "remaining_slots": [], "simulation_path": []}
        sim_sum, sim_weight = weighted_sum, total_weight
        path = []
        for idx, lesson in enumerate(remaining, 1):
            combined_weight = float(lesson["weight"]) * float(lesson.get("default_assessment_weight", 1))
            sim_sum += 10.0 * combined_weight
            sim_weight += combined_weight
            projected = sim_sum / sim_weight if sim_weight else 0.0
            path.append({"step": idx, "lesson_id": lesson["id"], "weight": combined_weight, "projected_gpa": projected})
            if projected + 1e-12 >= target:
                return {"student_id": student_id, "current_gpa": current, "target_gpa": target,
                        "required_consecutive_tens": idx, "strategic_alert": False, "alert_code": None,
                        "reachable": True, "projected_gpa": projected,
                        "remaining_slots": [l["id"] for l in remaining], "simulation_path": path}
        projected = sim_sum / sim_weight if sim_weight else current
        return {"student_id": student_id, "current_gpa": current, "target_gpa": target,
                "required_consecutive_tens": None, "strategic_alert": True,
                "alert_code": "TARGET_UNREACHABLE_WITH_REMAINING_CURRICULUM", "reachable": False,
                "projected_gpa": projected, "remaining_slots": [l["id"] for l in remaining],
                "simulation_path": path}


# --- ACA Platform professional animated interface --------------------------------------------
# UI dependencies: customtkinter >= 5.2, Pillow >= 10

try:
    import customtkinter as ctk
except Exception:
    ctk = None

# Localize standard dialogs without changing backend exception semantics.
if not getattr(messagebox, "_aca_ru_wrapped", False):
    for _name in ("showinfo", "showerror", "showwarning", "askyesno", "askokcancel"):
        _orig = getattr(messagebox, _name, None)
        if _orig is None:
            continue
        def _make_dialog_wrapper(fn):
            def _wrapped(title, message, *args, **kwargs):
                return fn(tr(title), tr_error(message), *args, **kwargs)
            return _wrapped
        setattr(messagebox, _name, _make_dialog_wrapper(_orig))
    messagebox._aca_ru_wrapped = True

def localize_widget_tree(root):
    if UI_LANGUAGE != "ru" or ctk is None:
        return
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
        for option in ("text", "placeholder_text"):
            try:
                current = widget.cget(option)
            except Exception:
                continue
            if isinstance(current, str) and current:
                translated = tr(current)
                if translated != current:
                    try:
                        widget.configure(**{option: translated})
                    except Exception:
                        pass

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

PREMIUM_UI = {
    "bg": "#020712",
    "sidebar": "#030B17",
    "surface": "#071321",
    "surface2": "#091827",
    "surface3": "#0D2239",
    "surface4": "#102C49",
    "line": "#12395E",
    "line_soft": "#0A2946",
    "card_border": "#1767A3",
    "card_border_soft": "#0D3C63",
    "table_header": "#0B2037",
    "text": "#F7FAFF",
    "text2": "#C8D6E8",
    "muted": "#748AA7",
    "cyan": "#2AD9FF",
    "cyan2": "#168BFF",
    "blue": "#2E72FF",
    "blue2": "#1556D9",
    "green": "#27E7B0",
    "green2": "#10C98F",
    "amber": "#FFD361",
    "pink": "#FF65C8",
    "red": "#FF617E",
    "violet": "#8B63FF",
    "violet2": "#6847EE",
    "selected": "#0B4386",
    "hover": "#0A2036",
    "glow": "#22CFFF",
    "deep": "#01060D",
}


FONT_UI = "SF Pro Display" if sys.platform == "darwin" else "Segoe UI"
FONT_MONO = "SF Mono" if sys.platform == "darwin" else "Consolas"


RU_TEXT.update({
    "Current section": "Текущий раздел",
    "Notifications": "Уведомления",
    "No notifications": "Нет уведомлений",
    "Recent activity": "Последние активности",
    "All activity": "Все действия",
    "Quick actions": "Быстрые действия",
    "Add grade": "Добавить оценку",
    "Create student": "Создать ученика",
    "Export report": "Экспорт отчёта",
    "Student profile": "Профиль ученика",
    "Progress by phase": "Прогресс по фазам",
    "Active now": "Активен",
    "Search lessons, grades, notes…": "Поиск уроков, оценок, заметок…",
    "Filters": "Фильтры",
    "Scale": "Масштаб",
    "View": "Вид",
    "Grade journal": "Журнал оценок",
    "Manage grades and student progress": "Управление оценками и прогрессом учеников",
    "Lesson details": "Данные урока",
    "No recent activity": "Последних действий пока нет",
    "System": "Система",
    "Profile": "Профиль",
    "Comment": "Комментарий",
    "Grade added": "Добавлена оценка",
    "Grade updated": "Оценка изменена",
    "Level ID updated": "Level ID обновлён",
    "Showcase URL updated": "Showcase URL обновлён",
    "Account role updated": "Роль аккаунта изменена",
    "Password reset": "Пароль сброшен",
    "Version": "Версия",
    "years": "лет",
})


def _fmt_grade(value):
    v = float(value)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _phase_accent(phase):
    return {
        1: "#61B9FF",
        2: "#4ED7C5",
        3: "#8B9CFF",
        4: "#B88CFF",
        5: "#FF9B68",
        6: "#FF6E90",
        7: "#E6C75C",
    }.get(int(phase), PREMIUM_UI["cyan"])


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _hex_rgb(value):
    value = str(value).lstrip("#")
    if len(value) != 6:
        return (49, 216, 255)
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def _neon_icon_pil(kind, size=28, color=None, glow=True):
    """Render smooth neon line art with high-resolution supersampling.

    Small Tk icons look rough when they are drawn directly at 18-28 px.  We draw
    at 10x resolution, use rounded caps/joins, build the halo from the alpha mask,
    then Lanczos-downsample once.  The final bitmap is already at display size so
    CustomTkinter does not need to invent intermediate pixels.
    """
    if not PIL_AVAILABLE:
        return None
    size = max(14, int(size))
    color = color or PREMIUM_UI["cyan"]
    rgb = _hex_rgb(color)
    scale = 10
    S = size * scale
    core = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(core)
    stroke = max(1.55, size * 0.068)
    w = max(2, int(round(stroke * scale)))
    c = (*rgb, 255)

    def _pt(x, y):
        return (int(round(x * scale)), int(round(y * scale)))

    def line(points, fill=c, width=w, caps=True):
        pts = [_pt(x, y) for x, y in points]
        d.line(pts, fill=fill, width=width, joint="curve")
        if caps and len(pts) >= 2:
            rr = width / 2
            for px, py in (pts[0], pts[-1]):
                d.ellipse((int(px-rr), int(py-rr), int(px+rr), int(py+rr)), fill=fill)

    def rect(box, radius=4.5, outline=c, width=w, fill=None):
        d.rounded_rectangle(
            tuple(int(round(v * scale)) for v in box),
            radius=max(1, int(round(radius * scale))),
            outline=outline, fill=fill, width=width,
        )

    def ellipse(box, outline=c, fill=None, width=w):
        d.ellipse(tuple(int(round(v * scale)) for v in box), outline=outline, fill=fill, width=width)

    def arc(box, start, end, fill=c, width=w):
        d.arc(tuple(int(round(v * scale)) for v in box), start, end, fill=fill, width=width)

    n = float(size)
    thin = max(2, int(round(w * .82)))

    if kind == "home":
        line([(4.8,n*.47),(n*.5,4.4),(n-4.8,n*.47)], width=thin)
        line([(7.6,n*.42),(7.6,n-4.8),(n-7.6,n-4.8),(n-7.6,n*.42)], width=thin)
        line([(n*.42,n-4.8),(n*.42,n*.66),(n*.59,n*.66),(n*.59,n-4.8)], width=max(2,int(w*.72)))
    elif kind == "journal":
        rect((5.7,3.8,n-5.7,n-3.8), radius=4.2, width=thin)
        for yy, x2 in ((9.6,n-10.5),(14.5,n-10.5),(19.4,n-13.5)):
            line([(10.5,yy),(x2,yy)], width=max(2,int(w*.70)))
    elif kind == "analytics":
        line([(4.8,n-4.8),(n-4.2,n-4.8)], width=max(2,int(w*.70)))
        for x,y in ((7,n*.55),(13,n*.34),(19,n*.18)):
            rect((x,y,x+4.2,n-6), radius=1.6, width=max(2,int(w*.72)))
    elif kind == "graduation":
        line([(n*.5,4.0),(n-4.8,n*.48),(n*.5,n-4.8),(4.8,n*.48),(n*.5,4.0)], width=thin)
        line([(9.6,n*.47),(n*.5,n*.60),(n-9.0,n*.43)], width=max(2,int(w*.72)))
    elif kind == "cap":
        line([(4.5,n*.40),(n*.5,5),(n-4.5,n*.40),(n*.5,n*.60),(4.5,n*.40)], width=thin)
        line([(8.2,n*.51),(8.2,n*.70),(n*.5,n*.80),(n-8.2,n*.70),(n-8.2,n*.51)], width=max(2,int(w*.70)))
        line([(n-5.3,n*.41),(n-5.3,n*.72)], width=max(2,int(w*.62)))
    elif kind == "clipboard":
        rect((6.0,6.2,n-6.0,n-4.5), radius=3.4, width=thin)
        rect((n*.36,3.6,n*.64,8.2), radius=2.0, width=max(2,int(w*.70)), fill=(*rgb,38))
        for yy in (12.0,16.8,21.3):
            line([(10.2,yy),(n-10.0,yy)], width=max(2,int(w*.64)))
    elif kind == "target":
        ellipse((4.3,4.3,n-4.3,n-4.3), width=thin)
        ellipse((8.4,8.4,n-8.4,n-8.4), width=max(2,int(w*.72)))
        line([(n*.50,n*.50),(n-4.5,4.5)], width=max(2,int(w*.70)))
        line([(n-7.0,4.5),(n-4.5,4.5),(n-4.5,7.0)], width=max(2,int(w*.70)))
    elif kind == "trend":
        line([(5,n-5),(5,6)], width=max(2,int(w*.65)))
        line([(5,n-5),(n-4,n-5)], width=max(2,int(w*.65)))
        line([(8,n-10),(n*.42,n*.56),(n*.60,n*.67),(n-6,8)], width=thin)
        line([(n-10,8),(n-6,8),(n-6,12)], width=max(2,int(w*.70)))
    elif kind == "access":
        ellipse((4.9,4.5,12.3,11.9), width=max(2,int(w*.78)))
        ellipse((15.7,4.5,23.1,11.9), width=max(2,int(w*.78)))
        arc((2.0,9.6,15.4,25.2), 205, 335, width=thin)
        arc((12.8,9.6,26.2,25.2), 205, 335, width=thin)
    elif kind == "security":
        line([(n*.5,3.8),(n-5.8,7.7),(n-6.8,n*.58),(n*.5,n-4.3),(6.8,n*.58),(5.8,7.7),(n*.5,3.8)], width=thin)
        line([(n*.37,n*.49),(n*.48,n*.60),(n*.68,n*.37)], width=max(2,int(w*.74)))
    elif kind == "backup":
        arc((4.8,7.0,n-4.8,n-4.8), 32, 332, width=thin)
        line([(n-8.1,5.9),(n-5.0,12.9),(n-12.0,11.8)], width=max(2,int(w*.74)))
    elif kind == "refresh":
        arc((4.8,4.8,n-4.8,n-4.8), 25, 315, width=thin)
        line([(n-8.0,5.4),(n-4.8,12.6),(n-12.1,11.5)], width=max(2,int(w*.74)))
    elif kind == "search":
        ellipse((4.8,4.8,n*.63,n*.63), width=thin)
        line([(n*.59,n*.59),(n-4.6,n-4.6)], width=thin)
    elif kind == "filter":
        line([(4.5,5.7),(n-4.5,5.7),(n*.60,n*.51),(n*.60,n-6.0),(n*.40,n-4.4),(n*.40,n*.51),(4.5,5.7)], width=thin)
    elif kind == "sliders":
        for yy, xx in ((7.0,10.0),(14.0,18.0),(21.0,13.0)):
            line([(4.2,yy),(n-4.2,yy)], width=max(2,int(w*.64)))
            ellipse((xx-2.2,yy-2.2,xx+2.2,yy+2.2), fill=c, outline=None, width=1)
    elif kind == "grid":
        for y in (5.1,15.0):
            for x in (5.1,15.0):
                rect((x,y,x+7.8,y+7.8),radius=2.2,width=max(2,int(w*.66)))
    elif kind == "plus":
        line([(n*.5,5),(n*.5,n-5)], width=thin)
        line([(5,n*.5),(n-5,n*.5)], width=thin)
    elif kind == "clock":
        ellipse((4.3,4.3,n-4.3,n-4.3), width=thin)
        line([(n*.5,n*.5),(n*.5,8.8),(n*.68,n*.60)], width=max(2,int(w*.70)))
    elif kind == "bolt":
        line([(n*.56,3.2),(8.1,n*.55),(n*.44,n*.55),(n*.35,n-3.2),(n-6.8,n*.40),(n*.59,n*.40),(n*.56,3.2)], width=thin)
    elif kind == "bell":
        arc((5.8,3.9,n-5.8,n-7.0), 195, 345, width=thin)
        line([(6.8,n-8.6),(n-6.8,n-8.6)], width=thin)
        ellipse((n*.455,n-7.1,n*.545,n-4.2),fill=c,outline=None,width=1)
    elif kind == "user":
        ellipse((n*.34,4.0,n*.66,n*.34), width=thin)
        arc((4.7,n*.25,n-4.7,n-4.2), 200, 340, width=thin)
    elif kind == "export":
        rect((5.0,8.0,n-5.0,n-4.5),radius=3.5,width=max(2,int(w*.72)))
        line([(n*.5,3.2),(n*.5,n*.58)], width=thin)
        line([(n*.34,n*.42),(n*.5,n*.58),(n*.66,n*.42)], width=max(2,int(w*.72)))
    elif kind == "book":
        rect((4.8,5.0,n-4.8,n-4.8),radius=3.8,width=thin)
        line([(n*.5,5.9),(n*.5,n-5.6)],width=max(2,int(w*.68)))
    else:
        ellipse((5,5,n-5,n-5), width=thin)
        line([(n*.5,9),(n*.5,n-9)], width=max(2,int(w*.70)))

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    if glow:
        alpha = core.getchannel("A")
        outer_a = alpha.filter(ImageFilter.GaussianBlur(max(2, int(size * .19 * scale))))
        inner_a = alpha.filter(ImageFilter.GaussianBlur(max(1, int(size * .08 * scale))))
        outer_a = outer_a.point(lambda a: int(a * .23))
        inner_a = inner_a.point(lambda a: int(a * .34))
        halo_outer = Image.new("RGBA", (S,S), (*rgb,0)); halo_outer.putalpha(outer_a)
        halo_inner = Image.new("RGBA", (S,S), (*rgb,0)); halo_inner.putalpha(inner_a)
        out = Image.alpha_composite(out, halo_outer)
        out = Image.alpha_composite(out, halo_inner)
    out = Image.alpha_composite(out, core)
    return out.resize((size,size), Image.Resampling.LANCZOS)


class LocalizedTooltip:
    """Small native tooltip whose text is resolved at show-time from RU/EN dictionaries."""
    def __init__(self, widget, key, delay_ms=420, wraplength=330):
        self.widget = widget
        self.key = key
        self.delay_ms = int(delay_ms)
        self.wraplength = int(wraplength)
        self._job = None
        self._tip = None
        self._bind_tree(widget)

    def _bind_tree(self, widget):
        try:
            widget.bind("<Enter>", self._enter, add="+")
            widget.bind("<Leave>", self._leave, add="+")
            widget.bind("<ButtonPress>", self._leave, add="+")
            for child in widget.winfo_children():
                self._bind_tree(child)
        except Exception:
            pass

    def _enter(self, _event=None):
        self._cancel()
        try:
            self._job = self.widget.after(self.delay_ms, self._show)
        except Exception:
            self._job = None

    def _leave(self, _event=None):
        self._cancel()
        self.hide()

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        self._job = None
        try:
            if not self.widget.winfo_exists():
                return
            text = tooltip_text(self.key)
            if not text:
                return
            self.hide()
            tip = tk.Toplevel(self.widget)
            self._tip = tip
            tip.wm_overrideredirect(True)
            try:
                tip.attributes("-topmost", True)
            except Exception:
                pass
            label = tk.Label(
                tip, text=text, justify="left", anchor="w",
                bg="#111A26", fg="#EAF2FC", relief="solid", bd=1,
                padx=10, pady=7, font=(FONT_UI, 10), wraplength=self.wraplength,
            )
            label.pack()
            tip.update_idletasks()
            x = self.widget.winfo_rootx() + min(18, max(0, self.widget.winfo_width() // 4))
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 7
            sw, sh = tip.winfo_screenwidth(), tip.winfo_screenheight()
            tw, th = tip.winfo_reqwidth(), tip.winfo_reqheight()
            x = max(4, min(x, sw - tw - 8))
            if y + th > sh - 8:
                y = max(4, self.widget.winfo_rooty() - th - 7)
            tip.wm_geometry(f"+{x}+{y}")
        except Exception:
            self.hide()

    def hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def attach_tooltip(widget, key, delay_ms=420):
    if widget is None:
        return None
    tip = LocalizedTooltip(widget, key, delay_ms=delay_ms)
    try:
        items = getattr(widget, "_aca_tooltips", None)
        if items is None:
            items = []
            setattr(widget, "_aca_tooltips", items)
        items.append(tip)
    except Exception:
        pass
    return tip


_BACKGROUND_CACHE = {}

def _soft_background_pil(width, height, variant="main"):
    """Create the soft blue/violet ambient background used by the polished shell."""
    if not PIL_AVAILABLE:
        return None
    width, height = max(8, int(width)), max(8, int(height))
    key = (width, height, str(variant))
    cached = _BACKGROUND_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    scale = 1.55
    sw, sh = int(width * scale), int(height * scale)
    base = Image.new("RGBA", (sw, sh), (*_hex_rgb(PREMIUM_UI["bg"]), 255))

    # Large radial light fields.  These are intentionally broad and low-opacity:
    # the reference looks luminous, not outlined.
    glow = Image.new("RGBA", (sw, sh), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    if variant in ("overview", "hero", "main"):
        gd.ellipse((sw*.48, -sh*.40, sw*1.16, sh*.63), fill=(22,133,255,92))
        gd.ellipse((sw*.69, -sh*.10, sw*1.22, sh*.82), fill=(101,62,255,68))
        gd.ellipse((-sw*.22, sh*.55, sw*.33, sh*1.26), fill=(20,210,255,25))
    elif variant == "journal":
        gd.ellipse((sw*.58, -sh*.24, sw*1.17, sh*.56), fill=(28,117,255,54))
        gd.ellipse((sw*.72, sh*.56, sw*1.22, sh*1.22), fill=(90,54,255,42))
        gd.ellipse((-sw*.18, sh*.62, sw*.30, sh*1.22), fill=(0,191,255,18))
    elif variant == "sidebar":
        gd.ellipse((-sw*.52, sh*.53, sw*.70, sh*1.23), fill=(14,103,255,54))
        gd.ellipse((-sw*.18, sh*.73, sw*.86, sh*1.30), fill=(103,48,255,38))
    else:
        gd.ellipse((sw*.58, -sh*.30, sw*1.18, sh*.58), fill=(22,115,255,42))
        gd.ellipse((sw*.74, sh*.55, sw*1.22, sh*1.16), fill=(93,57,255,30))
    glow = glow.filter(ImageFilter.GaussianBlur(max(24, int(min(sw,sh)*.11))))
    base = Image.alpha_composite(base, glow)

    # Wide luminous ribbons create the soft flowing background from the reference.
    ribbons = Image.new("RGBA", (sw, sh), (0,0,0,0))
    rd = ImageDraw.Draw(ribbons)
    def ribbon(y0, amp, cycles, phase, color, width_ratio):
        pts=[]
        for i in range(181):
            t=i/180.0; x=t*sw
            y=y0 + amp*math.sin((t*cycles+phase)*math.tau) + amp*.22*math.sin((t*cycles*.48+phase*.4)*math.tau)
            pts.append((int(x),int(y)))
        rd.line(pts, fill=color, width=max(2,int(sh*width_ratio)), joint="curve")
    if variant in ("overview","hero"):
        ribbon(sh*.30,sh*.11,.52,.12,(13,112,255,68),.24)
        ribbon(sh*.38,sh*.10,.58,.29,(76,67,255,54),.19)
        ribbon(sh*.95,sh*.06,.62,.40,(16,131,255,34),.15)
    elif variant == "journal":
        ribbon(sh*.88,sh*.07,.62,.18,(17,117,255,24),.16)
        ribbon(sh*.95,sh*.05,.70,.38,(86,64,255,20),.12)
    elif variant == "sidebar":
        ribbon(sh*.86,sh*.08,.55,.14,(15,104,255,38),.19)
        ribbon(sh*.93,sh*.065,.61,.32,(91,57,255,34),.15)
    ribbons = ribbons.filter(ImageFilter.GaussianBlur(max(10,int(min(sw,sh)*.055))))
    base = Image.alpha_composite(base, ribbons)

    # Fine ribbon highlights, rendered large and then downsampled.
    waves = Image.new("RGBA", (sw, sh), (0,0,0,0))
    wd = ImageDraw.Draw(waves)
    def wave(y0, amp, cycles, phase, color, width_px):
        pts=[]
        for i in range(161):
            x = i/160.0 * sw
            t = i/160.0
            y = y0 + amp*math.sin((t*cycles+phase)*math.tau) + amp*.26*math.sin((t*cycles*.43+phase*.7)*math.tau)
            pts.append((int(x), int(y)))
        wd.line(pts, fill=color, width=max(1,int(width_px)), joint="curve")

    if variant == "sidebar":
        wave(sh*.84, sh*.075, .52, .08, (18,111,255,92), 2.0*scale)
        wave(sh*.90, sh*.060, .58, .24, (71,70,255,78), 1.6*scale)
        wave(sh*.95, sh*.045, .62, .44, (125,56,255,65), 1.2*scale)
    else:
        wave(sh*.83, sh*.055, .72, .10, (11,126,255,40), 1.5*scale)
        wave(sh*.90, sh*.043, .78, .28, (85,64,255,34), 1.2*scale)
        if variant in ("overview", "hero"):
            wave(sh*.27, sh*.075, .56, .18, (31,145,255,45), 1.4*scale)
            wave(sh*.31, sh*.066, .62, .34, (83,69,255,34), 1.1*scale)

    soft = waves.filter(ImageFilter.GaussianBlur(max(5, int(5*scale))))
    base = Image.alpha_composite(base, soft)
    base = Image.alpha_composite(base, waves)
    result = base.resize((width,height), Image.Resampling.LANCZOS)
    _BACKGROUND_CACHE[key] = result.copy()
    # Keep resize churn bounded; hidden pages share the same cached main backdrop.
    while len(_BACKGROUND_CACHE) > 10:
        _BACKGROUND_CACHE.pop(next(iter(_BACKGROUND_CACHE)))
    return result


class SmoothBackdrop(tk.Canvas):
    """Resize-aware PIL backdrop; visual only and deliberately non-interactive."""
    def __init__(self, master, variant="main"):
        super().__init__(master, bg=PREMIUM_UI["bg"], bd=0, highlightthickness=0, takefocus=0)
        self.variant = variant
        self._img = None
        self._job = None
        self.bind("<Configure>", self._schedule, add="+")

    def lower_widget(self, below_this=None):
        """Lower the Canvas *widget* rather than a canvas item.

        tkinter.Canvas aliases ``lower`` to ``tag_lower``; calling ``lower()``
        on a Canvas therefore expects a canvas tag/item id and raises TclError
        when used for widget stacking. Explicitly dispatch through tk.Misc.
        """
        return tk.Misc.lower(self, below_this)

    def raise_widget(self, above_this=None):
        """Raise the Canvas widget without invoking Canvas.tag_raise."""
        return tk.Misc.lift(self, above_this)

    def _schedule(self, _event=None):
        if self._job is not None:
            try: self.after_cancel(self._job)
            except Exception: pass
        self._job = self.after(70, self._redraw)

    def _redraw(self):
        self._job = None
        if not PIL_AVAILABLE or not self.winfo_exists():
            return
        w, h = max(20,self.winfo_width()), max(20,self.winfo_height())
        image = _soft_background_pil(w,h,self.variant)
        if image is None:
            return
        self._img = ImageTk.PhotoImage(image)
        self.delete("all")
        self.create_image(0,0,image=self._img,anchor="nw")


def _rounded_mask(width, height, radius, scale=4):
    sw, sh = max(1,int(width*scale)), max(1,int(height*scale))
    mask = Image.new("L", (sw,sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,sw-1,sh-1), radius=int(radius*scale), fill=255)
    return mask.resize((width,height), Image.Resampling.LANCZOS)


def _catmull_rom(points, samples=14):
    if len(points) < 3:
        return points
    pts=[points[0]]+list(points)+[points[-1]]
    out=[]
    for i in range(1,len(pts)-2):
        p0,p1,p2,p3=pts[i-1],pts[i],pts[i+1],pts[i+2]
        for step in range(samples):
            t=step/float(samples); t2=t*t; t3=t2*t
            x=.5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2+(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y=.5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2+(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            out.append((x,y))
    out.append(points[-1])
    return out


class HeroPanel(tk.Canvas):
    def __init__(self, master, app, height=224):
        super().__init__(master, height=height, bg=PREMIUM_UI["bg"], bd=0, highlightthickness=0)
        self.app = app
        self._img = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def _make_background(self, w, h, chip_box=None):
        if not PIL_AVAILABLE:
            return None
        art = _soft_background_pil(w, h, "hero")
        if art is None:
            return None
        # Slightly lift the panel above the page and anti-alias the radius/border.
        shade = Image.new("RGBA", art.size, (7,18,32,74))
        art = Image.alpha_composite(art.convert("RGBA"), shade)
        art.putalpha(_rounded_mask(w,h,24,scale=5))

        overlay_scale=4
        ow,oh=w*overlay_scale,h*overlay_scale
        ov=Image.new("RGBA",(ow,oh),(0,0,0,0)); od=ImageDraw.Draw(ov)
        od.rounded_rectangle((2*overlay_scale,2*overlay_scale,ow-3*overlay_scale,oh-3*overlay_scale),
                             radius=22*overlay_scale,outline=(31,115,181,125),width=1*overlay_scale)
        if chip_box:
            x1,y1,x2,y2=chip_box
            od.rounded_rectangle(tuple(int(v*overlay_scale) for v in (x1,y1,x2,y2)),
                                 radius=15*overlay_scale,fill=(5,20,37,226),outline=(63,117,176,150),width=1*overlay_scale)
        ov=ov.resize((w,h),Image.Resampling.LANCZOS)
        art=Image.alpha_composite(art,ov)
        return ImageTk.PhotoImage(art)

    def redraw(self):
        self.delete("all")
        w, h = max(260, self.winfo_width()), max(180, self.winfo_height())
        chip_w, chip_h = 138, 84
        chip_x, chip_y = w-chip_w-28, 28
        if PIL_AVAILABLE:
            self._img = self._make_background(w,h,(chip_x,chip_y,chip_x+chip_w,chip_y+chip_h))
            if self._img: self.create_image(0,0,image=self._img,anchor="nw")
        else:
            self.create_rectangle(0,0,w,h,fill=PREMIUM_UI["surface"],outline="")

        sid=self.app.active_sid(); student=self.app.model.get_student(sid) if sid else None
        if not student:
            self.create_text(34,42,text="APEX CREATOR ACADEMY",fill=PREMIUM_UI["cyan"],font=(FONT_MONO,10,"bold"),anchor="w")
            self.create_text(34,88,text=tr("Create your first student profile"),fill=PREMIUM_UI["text"],font=(FONT_UI,28,"bold"),anchor="w")
            self.create_text(34,128,text=tr("The dashboard will populate with GPA, progress and phase analytics."),fill=PREMIUM_UI["text2"],font=(FONT_UI,12),anchor="w")
            return

        gpa=self.app.model.weighted_gpa(sid); progress=self.app.model.progress(sid); badge=self.app.model.badge(sid); grades=self.app.model.total_grade_count(sid)
        self.create_text(34,34,text=tr("STUDENT COMMAND CENTER"),fill=PREMIUM_UI["cyan"],font=(FONT_MONO,10,"bold"),anchor="w")
        self.create_text(34,78,text=student.get("name",tr("Student")),fill=PREMIUM_UI["text"],font=(FONT_UI,30,"bold"),anchor="w")
        meta=f"{tr(student.get('skill_class','Unranked'))}  •  {localized_grade_count(grades)}  •  {tr(badge)}"
        self.create_text(34,114,text=meta,fill=PREMIUM_UI["text2"],font=(FONT_UI,11),anchor="w")

        bar_x1,bar_y,bar_x2=34,h-43,max(310,w-355)
        self.create_line(bar_x1,bar_y,bar_x2,bar_y,fill="#203751",width=10,capstyle="round")
        px=bar_x1+(bar_x2-bar_x1)*clamp(progress,0.0,1.0)
        self.create_line(bar_x1,bar_y,px,bar_y,fill="#28D9FF",width=10,capstyle="round")
        self.create_text(bar_x1,bar_y-20,text=f"{tr('Curriculum completion')}  {progress*100:.1f}%",fill="#89A1BE",font=(FONT_UI,10,"bold"),anchor="w")

        self.create_text(chip_x+17,chip_y+20,text=tr("WEIGHTED GPA"),fill="#8198B5",font=(FONT_MONO,8,"bold"),anchor="w")
        gpa_color=PREMIUM_UI["green"] if gpa>=8.9 else PREMIUM_UI["amber"] if gpa>=6 else PREMIUM_UI["pink"]
        self.create_text(chip_x+17,chip_y+57,text=f"{gpa:.3f}",fill=gpa_color,font=(FONT_MONO,24,"bold"),anchor="w")


class GPAChart(tk.Canvas):
    def __init__(self, master, app, height=260):
        super().__init__(master, height=height, bg=PREMIUM_UI["surface"], bd=0, highlightthickness=0)
        self.app=app; self._plot_img=None
        self.bind("<Configure>", lambda _e:self.draw_chart())

    def _render_layer(self,w,h,series):
        if not PIL_AVAILABLE: return None
        scale=3; sw,sh=w*scale,h*scale
        layer=Image.new("RGBA",(sw,sh),(0,0,0,0)); d=ImageDraw.Draw(layer)
        pad_l,pad_r,pad_t,pad_b=42,20,24,34
        for tick in range(0,11,2):
            y=h-pad_b-(tick/10.0)*(h-pad_t-pad_b)
            d.line(((pad_l*scale,int(y*scale)),((w-pad_r)*scale,int(y*scale))),fill=(22,65,100,115),width=max(1,scale))
        if series:
            max_x=max(1,series[-1][0]-1); pts=[]
            for idx,gpa in series:
                rx=(idx-1)/max_x if max_x else 0.0
                x=pad_l+rx*(w-pad_l-pad_r); y=h-pad_b-(gpa/10.0)*(h-pad_t-pad_b)
                pts.append((x,y))
            smooth=_catmull_rom(pts,18) if len(pts)>=3 else pts
            sp=[(int(x*scale),int(y*scale)) for x,y in smooth]
            if len(sp)>=2:
                glow=Image.new("RGBA",(sw,sh),(0,0,0,0)); gd=ImageDraw.Draw(glow)
                gd.line(sp,fill=(42,217,255,150),width=7*scale,joint="curve")
                glow=glow.filter(ImageFilter.GaussianBlur(5*scale))
                layer=Image.alpha_composite(layer,glow); d=ImageDraw.Draw(layer)
                d.line(sp,fill=(42,217,255,255),width=max(2,2*scale),joint="curve")
            for x,y in pts:
                xx,yy=int(x*scale),int(y*scale); r=3*scale
                d.ellipse((xx-r,yy-r,xx+r,yy+r),fill=(39,231,176,255))
            x,y=pts[-1]; xx,yy=int(x*scale),int(y*scale); r=6*scale
            d.ellipse((xx-r,yy-r,xx+r,yy+r),fill=(*_hex_rgb(PREMIUM_UI["surface"]),255),outline=(42,217,255,255),width=2*scale)
        return layer.resize((w,h),Image.Resampling.LANCZOS)

    def draw_chart(self):
        self.delete("all"); w,h=max(320,self.winfo_width()),max(180,self.winfo_height())
        sid=self.app.active_sid(); series=self.app.model.gpa_series(sid) if sid else []
        image=self._render_layer(w,h,series)
        if image is not None:
            self._plot_img=ImageTk.PhotoImage(image); self.create_image(0,0,image=self._plot_img,anchor="nw")
        pad_l,pad_r,pad_t,pad_b=42,20,24,34
        for tick in range(0,11,2):
            y=h-pad_b-(tick/10.0)*(h-pad_t-pad_b)
            self.create_text(12,y,text=str(tick),fill=PREMIUM_UI["muted"],font=(FONT_MONO,8),anchor="w")
        if not series:
            self.create_text(w/2,h/2,text=tr("No grade history yet"),fill=PREMIUM_UI["muted"],font=(FONT_UI,11,"bold"))


class ProjectionChart(tk.Canvas):
    def __init__(self, master, app, height=290):
        super().__init__(master, height=height, bg=PREMIUM_UI["surface"], bd=0, highlightthickness=0)
        self.app=app; self.result=None; self._plot_img=None
        self.bind("<Configure>", lambda _e:self.redraw())

    def set_result(self,result): self.result=result; self.redraw()

    def redraw(self):
        self.delete("all"); w,h=max(300,self.winfo_width()),max(200,self.winfo_height())
        pad_l,pad_r,pad_t,pad_b=44,20,26,34
        values=[]; target=None
        if self.result:
            path=self.result.get("simulation_path",[]); values=[float(self.result.get("current_gpa",0.0))]+[float(p["projected_gpa"]) for p in path]
            target=float(self.result.get("target_gpa",8.9))
        if PIL_AVAILABLE:
            scale=3; sw,sh=w*scale,h*scale
            layer=Image.new("RGBA",(sw,sh),(0,0,0,0)); d=ImageDraw.Draw(layer)
            for tick in (0,2,4,6,8,10):
                y=h-pad_b-tick/10.0*(h-pad_t-pad_b)
                d.line(((pad_l*scale,int(y*scale)),((w-pad_r)*scale,int(y*scale))),fill=(22,65,100,115),width=scale)
            if target is not None:
                ty=h-pad_b-target/10.0*(h-pad_t-pad_b)
                dash=6*scale; gap=5*scale; x0=pad_l*scale; x1=(w-pad_r)*scale; y=int(ty*scale)
                x=x0
                while x<x1:
                    d.line((x,y,min(x+dash,x1),y),fill=(255,211,97,165),width=scale)
                    x+=dash+gap
            if values:
                max_x=max(1,len(values)-1); pts=[]
                for i,gpa in enumerate(values):
                    x=pad_l+(i/max_x)*(w-pad_l-pad_r); y=h-pad_b-(gpa/10.0)*(h-pad_t-pad_b); pts.append((x,y))
                smooth=_catmull_rom(pts,18) if len(pts)>=3 else pts
                sp=[(int(x*scale),int(y*scale)) for x,y in smooth]
                if len(sp)>=2:
                    glow=Image.new("RGBA",(sw,sh),(0,0,0,0)); gd=ImageDraw.Draw(glow)
                    gd.line(sp,fill=(39,231,176,125),width=7*scale,joint="curve")
                    glow=glow.filter(ImageFilter.GaussianBlur(5*scale)); layer=Image.alpha_composite(layer,glow); d=ImageDraw.Draw(layer)
                    d.line(sp,fill=(39,231,176,255),width=2*scale,joint="curve")
                for x,y in pts:
                    xx,yy=int(x*scale),int(y*scale); r=3*scale
                    d.ellipse((xx-r,yy-r,xx+r,yy+r),fill=(39,231,176,255))
            image=layer.resize((w,h),Image.Resampling.LANCZOS); self._plot_img=ImageTk.PhotoImage(image); self.create_image(0,0,image=self._plot_img,anchor="nw")
        for tick in (0,2,4,6,8,10):
            y=h-pad_b-tick/10.0*(h-pad_t-pad_b); self.create_text(12,y,text=str(tick),fill=PREMIUM_UI["muted"],font=(FONT_MONO,8),anchor="w")
        if target is not None:
            ty=h-pad_b-target/10.0*(h-pad_t-pad_b); self.create_text(w-pad_r-4,ty-10,text=f"{tr('TARGET')} {target:.2f}",fill=PREMIUM_UI["amber"],font=(FONT_MONO,8,"bold"),anchor="e")
        if not self.result:
            self.create_text(w/2,h/2,text=tr("Run the clutch simulator to draw the projection"),fill=PREMIUM_UI["muted"],font=(FONT_UI,10,"bold"))


class PremiumGradeGrid(tk.Frame):
    """Professional desktop grade sheet for the fixed 120-lesson curriculum.

    Architecture deliberately mirrors a native spreadsheet: the lesson directory and
    its header are physically separate canvases from the horizontally scrollable grade
    history. Vertical movement is synchronized; horizontal movement never touches the
    pinned lesson pane. View controls are transient and never mutate student data.
    """
    BASE_ROW_H = 64
    BASE_HEADER_H = 66
    BASE_LEFT_W = 520
    BASE_GRADE_W = 122
    MIN_ZOOM = 75
    MAX_ZOOM = 150
    DENSITY = {"Compact": 0.82, "Comfort": 1.0, "Spacious": 1.18}

    def __init__(self, master, app):
        super().__init__(master, bg=PREMIUM_UI["surface"], bd=0)
        self.app = app
        self.phase_filter = 0
        self.status_filter = "All"
        self.search_filter = ""
        self.zoom = 1.0
        self.density = "Comfort"
        self.selected = None
        self.hovered = None
        self.rows = list(CURRICULUM)
        self._flash_job = None
        self._pan_active = False
        self._last_pointer = None
        self._build()

    @property
    def density_factor(self):
        return self.DENSITY.get(self.density, 1.0)

    @property
    def ROW_H(self):
        return max(40, int(self.BASE_ROW_H * self.zoom * self.density_factor))

    @property
    def HEADER_H(self):
        return max(52, int(self.BASE_HEADER_H * min(self.zoom, 1.22)))

    @property
    def LEFT_W(self):
        # Keep the frozen pane stable enough to read at every zoom level.
        return max(430, min(650, int(self.BASE_LEFT_W * (0.88 + 0.12 * self.zoom))))

    @property
    def GRADE_W(self):
        return max(86, int(self.BASE_GRADE_W * self.zoom))

    def _build(self):
        self.header_left = tk.Canvas(
            self, width=self.LEFT_W, height=self.HEADER_H,
            bg="#121C28", bd=0, highlightthickness=0,
        )
        self.header_right = tk.Canvas(
            self, height=self.HEADER_H, bg="#121C28",
            bd=0, highlightthickness=0,
        )
        self.left = tk.Canvas(
            self, width=self.LEFT_W, bg=PREMIUM_UI["surface"],
            bd=0, highlightthickness=0, takefocus=1,
        )
        self.right = tk.Canvas(
            self, bg=PREMIUM_UI["surface"], bd=0,
            highlightthickness=0, cursor="hand2", takefocus=1,
        )
        self.footer_left = tk.Canvas(
            self, width=self.LEFT_W, height=24, bg="#0D1520",
            bd=0, highlightthickness=0,
        )

        self.vbar = ctk.CTkScrollbar(
            self, orientation="vertical", width=13, corner_radius=7,
            fg_color=PREMIUM_UI["surface"], button_color="#304259",
            button_hover_color=PREMIUM_UI["cyan2"], command=self._yview,
        )
        self.hbar = ctk.CTkScrollbar(
            self, orientation="horizontal", height=13, corner_radius=7,
            fg_color=PREMIUM_UI["surface"], button_color="#304259",
            button_hover_color=PREMIUM_UI["cyan2"], command=self._xview,
        )

        self.header_left.grid(row=0, column=0, sticky="nsew")
        self.header_right.grid(row=0, column=1, sticky="ew")
        self.left.grid(row=1, column=0, sticky="nsew")
        self.right.grid(row=1, column=1, sticky="nsew")
        self.vbar.grid(row=1, column=2, sticky="ns", padx=(7, 0), pady=(2, 2))
        self.footer_left.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.hbar.grid(row=2, column=1, sticky="ew", pady=(6, 0))
        self.grid_columnconfigure(0, minsize=self.LEFT_W)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.right.configure(yscrollcommand=self._on_y_scroll, xscrollcommand=self._on_x_scroll)
        self.left.configure(yscrollcommand=lambda _a, _b: None)

        for widget in (self.left, self.right):
            widget.bind("<MouseWheel>", self._wheel)
            widget.bind("<Button-4>", lambda _e: self._linux_wheel(-1))
            widget.bind("<Button-5>", lambda _e: self._linux_wheel(1))
            widget.bind("<Control-MouseWheel>", self._zoom_wheel)
            widget.bind("<Command-MouseWheel>", self._zoom_wheel)
            widget.bind("<Button-1>", lambda e, w=widget: w.focus_set(), add="+")
            widget.bind("<KeyPress-Up>", lambda e: self._key_move(0, -1))
            widget.bind("<KeyPress-Down>", lambda e: self._key_move(0, 1))
            widget.bind("<KeyPress-Left>", lambda e: self._key_move(-1, 0))
            widget.bind("<KeyPress-Right>", lambda e: self._key_move(1, 0))
            widget.bind("<KeyPress-Prior>", lambda e: self._key_page(-1))
            widget.bind("<KeyPress-Next>", lambda e: self._key_page(1))
            widget.bind("<KeyPress-Home>", lambda e: self._key_home_end(False))
            widget.bind("<KeyPress-End>", lambda e: self._key_home_end(True))
            widget.bind("<Return>", self._key_edit)
            widget.bind("<KP_Enter>", self._key_edit)

        self.right.bind("<Shift-MouseWheel>", self._shift_wheel)
        self.right.bind("<Button-1>", self._single_click, add="+")
        self.right.bind("<Double-1>", self._double_click)
        self.right.bind("<Motion>", self._motion)
        self.right.bind("<Leave>", self._leave)
        self.left.bind("<Motion>", self._left_motion)
        self.left.bind("<Leave>", self._leave)
        self.left.bind("<Button-1>", self._left_click, add="+")
        self.left.bind("<Double-1>", self._left_double_click)

        # Middle-button drag gives mouse users a spreadsheet-style pan interaction.
        self.right.bind("<ButtonPress-2>", self._pan_start)
        self.right.bind("<B2-Motion>", self._pan_drag)
        self.right.bind("<ButtonRelease-2>", self._pan_end)

        self.render()

    def set_phase(self, phase):
        self.phase_filter = int(phase)
        self.selected = None
        self.render(reset_y=True)

    def set_status_filter(self, status):
        valid = ("All", "Graded", "Active", "Empty", "At risk")
        self.status_filter = status if status in valid else "All"
        self.selected = None
        self.render(reset_y=True)

    def set_search_filter(self, value):
        value = str(value or "").strip().lower()
        if value == self.search_filter:
            return
        self.search_filter = value
        self.selected = None
        self.render(reset_y=True)

    def set_density(self, value):
        value = str(value or "Comfort")
        if value not in self.DENSITY or value == self.density:
            return
        old_y = self.right.yview()[0] if self.right.yview() else 0.0
        self.density = value
        self.render()
        self._yview("moveto", old_y)
        self.app.set_status(f"{tr('Journal density: ')}{tr(value)}")

    def set_zoom(self, percent):
        try:
            pct = int(round(float(str(percent).replace("%", "").strip())))
        except Exception:
            pct = 100
        pct = max(self.MIN_ZOOM, min(self.MAX_ZOOM, pct))
        new_zoom = pct / 100.0
        if abs(new_zoom - self.zoom) < 1e-9:
            self._sync_zoom_controls(pct)
            return
        old_y = self.right.yview()[0] if self.right.yview() else 0.0
        old_x = self.right.xview()[0] if self.right.xview() else 0.0
        self.zoom = new_zoom
        self.header_left.configure(width=self.LEFT_W, height=self.HEADER_H)
        self.header_right.configure(height=self.HEADER_H)
        self.left.configure(width=self.LEFT_W)
        self.footer_left.configure(width=self.LEFT_W)
        self.grid_columnconfigure(0, minsize=self.LEFT_W)
        self.render()
        self._yview("moveto", old_y)
        self._xview("moveto", old_x)
        self._sync_zoom_controls(pct)
        self.app.set_status(f"Journal zoom {pct}%")

    def _sync_zoom_controls(self, pct):
        if hasattr(self.app, "journal_zoom_value"):
            self.app.journal_zoom_value.configure(text=f"{pct}%")
        if hasattr(self.app, "journal_zoom_slider"):
            try:
                self.app.journal_zoom_slider.set(pct)
            except Exception:
                pass

    def fit_zoom(self):
        # Fit targets a dense but legible spreadsheet view rather than trying to
        # squeeze an unbounded transaction history into the viewport.
        self.set_zoom(90)

    def reset_view(self):
        self.phase_filter = 0
        self.status_filter = "All"
        self.search_filter = ""
        self.density = "Comfort"
        self.zoom = 1.0
        self.selected = None
        if hasattr(self.app, "phase_segment"):
            self.app.phase_segment.set(tr("All"))
        if hasattr(self.app, "journal_status_segment"):
            self.app.journal_status_segment.set(tr("All"))
        if hasattr(self.app, "journal_search_var"):
            self.app.journal_search_var.set("")
        if hasattr(self.app, "journal_density_segment"):
            self.app.journal_density_segment.set(tr("Comfort"))
        self._sync_zoom_controls(100)
        self.render(reset_y=True)
        self._xview("moveto", 0.0)
        self.app.set_status("Journal view reset")

    def _zoom_wheel(self, event):
        direction = 1 if getattr(event, "delta", 0) > 0 else -1
        pct = int(round(self.zoom * 100 / 5) * 5) + direction * 5
        self.set_zoom(pct)
        return "break"

    def _visible_rows(self):
        sid = self.app.active_sid()
        active_lesson = self.app.model.active_lesson_id(sid) if sid else None
        threshold = float(self.app.model.settings.get("probation_threshold", 8.9))
        result = []
        for lesson in CURRICULUM:
            if self.phase_filter and lesson["phase"] != self.phase_filter:
                continue
            if self.search_filter:
                haystack = " ".join((lesson["id"], lesson["name"], localize_lesson_name(lesson["name"]), lesson["type"], tr(lesson["type"]), lesson["phase_name"], tr(lesson["phase_name"]))).lower()
                if self.search_filter not in haystack:
                    continue
            grades = self.app.model.get_grades(sid, lesson["id"]) if sid else []
            if self.status_filter == "Graded" and not grades:
                continue
            if self.status_filter == "Empty" and grades:
                continue
            if self.status_filter == "Active" and lesson["id"] != active_lesson:
                continue
            if self.status_filter == "At risk":
                if not grades:
                    continue
                avg = sum(float(g.get("effective_grade", g.get("grade", 0))) for g in grades) / len(grades)
                if avg >= threshold:
                    continue
            result.append(lesson)
        return result

    def _max_cols(self, sid):
        maximum = 0
        if sid:
            for lesson in self.rows:
                maximum = max(maximum, len(self.app.model.get_grades(sid, lesson["id"])))
        return max(8, maximum + 3)

    def _yview(self, *args):
        self.left.yview(*args)
        self.right.yview(*args)

    def _xview(self, *args):
        self.right.xview(*args)
        self.header_right.xview(*args)
        self._update_view_info()

    def _on_y_scroll(self, first, last):
        self.vbar.set(first, last)
        self.left.yview_moveto(first)
        self._update_view_info()

    def _on_x_scroll(self, first, last):
        self.hbar.set(first, last)
        self.header_right.xview_moveto(first)
        self._update_view_info()

    def _wheel(self, event):
        state = getattr(event, "state", 0)
        if state & 0x0004:
            return self._zoom_wheel(event)
        delta = getattr(event, "delta", 0)
        if sys.platform == "darwin":
            steps = -max(-7, min(7, int(delta))) if delta else 0
        else:
            steps = -int(delta / 120) if delta else 0
        if steps:
            self._yview("scroll", steps, "units")
        return "break"

    def _linux_wheel(self, direction):
        self._yview("scroll", direction, "units")
        return "break"

    def _shift_wheel(self, event):
        delta = getattr(event, "delta", 0)
        if sys.platform == "darwin":
            steps = -max(-7, min(7, int(delta))) if delta else 0
        else:
            steps = -int(delta / 120) if delta else 0
        if steps:
            self._xview("scroll", steps, "units")
        return "break"

    def scroll_x(self, direction):
        self._xview("scroll", int(direction) * 3, "units")

    def _pan_start(self, event):
        self._pan_active = True
        self.right.scan_mark(event.x, event.y)
        self.right.configure(cursor="fleur")
        return "break"

    def _pan_drag(self, event):
        if not self._pan_active:
            return "break"
        self.right.scan_dragto(event.x, event.y, gain=1)
        x = self.right.xview()[0] if self.right.xview() else 0.0
        y = self.right.yview()[0] if self.right.yview() else 0.0
        self.header_right.xview_moveto(x)
        self.left.yview_moveto(y)
        self._update_view_info()
        return "break"

    def _pan_end(self, _event=None):
        self._pan_active = False
        self.right.configure(cursor="hand2")
        return "break"

    def _row_from_y(self, canvas, y):
        cy = canvas.canvasy(y)
        ri = int(cy // self.ROW_H)
        if 0 <= ri < len(self.rows):
            return self.rows[ri], ri
        return None, None

    def _cell_from_event(self, event):
        sid = self.app.active_sid()
        if not sid:
            return None
        lesson, ri = self._row_from_y(self.right, event.y)
        if lesson is None:
            return None
        x = self.right.canvasx(event.x)
        ci = int(x // self.GRADE_W)
        if ci < 0:
            return None
        return lesson, ci, ri

    def _left_click(self, event):
        lesson, ri = self._row_from_y(self.left, event.y)
        if not lesson:
            return
        self.selected = (lesson["id"], 0)
        self.app.set_inspector_lesson(lesson["id"])
        self.render_body()
        self._flash_cell(ri, 0)

    def _single_click(self, event):
        cell = self._cell_from_event(event)
        if not cell:
            return
        lesson, col, row_index = cell
        self.selected = (lesson["id"], col)
        self.app.set_inspector_lesson(lesson["id"])
        self.render_body()
        self._flash_cell(row_index, col)

    def _double_click(self, event):
        cell = self._cell_from_event(event)
        if not cell:
            return
        lesson, col, _row_index = cell
        grades = self.app.model.get_grades(self.app.active_sid(), lesson["id"])
        self.app.open_grade_modal(lesson["id"], col if col < len(grades) else None)

    def _left_double_click(self, event):
        lesson, _ri = self._row_from_y(self.left, event.y)
        if lesson:
            grades = self.app.model.get_grades(self.app.active_sid(), lesson["id"])
            self.app.set_inspector_lesson(lesson["id"])
            self.app.open_grade_modal(lesson["id"], len(grades))

    def _left_motion(self, event):
        lesson, ri = self._row_from_y(self.left, event.y)
        if lesson is None:
            self._leave()
            return
        key = (lesson["id"], None)
        if self.hovered != key:
            self.hovered = key
            self._draw_hover(ri, None)
        self.app.set_status(tr(f"{lesson['id']} • {localize_lesson_name(lesson['name'])} • double-click to append grade"))

    def _motion(self, event):
        cell = self._cell_from_event(event)
        if not cell:
            self._leave()
            return
        lesson, col, ri = cell
        key = (lesson["id"], col)
        if self.hovered != key:
            self.hovered = key
            self._draw_hover(ri, col)
        grades = self.app.model.get_grades(self.app.active_sid(), lesson["id"])
        if col < len(grades):
            entry = grades[col]
            self.app.set_status(
                f"{lesson['id']} • Grade {col+1}: {_fmt_grade(entry.get('grade', 0))}/10 "
                f"• weight ×{entry.get('weight_multiplier', 1)} • double-click to edit"
            )
        else:
            self.app.set_status(f"{lesson['id']} • empty grade slot • double-click to add")

    def _leave(self, _event=None):
        self.hovered = None
        self.left.delete("hover_left")
        self.right.delete("hover_right")
        self.app.set_status("")

    def _draw_hover(self, row_index, col):
        self.left.delete("hover_left")
        self.right.delete("hover_right")
        y1, y2 = row_index * self.ROW_H, (row_index + 1) * self.ROW_H
        self.left.create_rectangle(2, y1 + 2, self.LEFT_W - 4, y2 - 2,
                                   outline="#355B74", width=1, tags="hover_left")
        if col is not None:
            x1, x2 = col * self.GRADE_W, (col + 1) * self.GRADE_W
            self.right.create_rectangle(x1 + 4, y1 + 5, x2 - 4, y2 - 5,
                                        outline="#355B74", width=1, tags="hover_right")

    def _flash_cell(self, row_index, col):
        self.right.delete("selection_flash")
        y1, y2 = row_index * self.ROW_H, (row_index + 1) * self.ROW_H
        x1, x2 = col * self.GRADE_W, (col + 1) * self.GRADE_W
        self.right.create_rectangle(x1 + 2, y1 + 3, x2 - 2, y2 - 3,
                                    outline=PREMIUM_UI["cyan"], width=2,
                                    tags="selection_flash")
        if self._flash_job:
            try:
                self.after_cancel(self._flash_job)
            except Exception:
                pass
        self._flash_job = self.after(130, lambda: self.right.delete("selection_flash"))

    def _selected_indices(self):
        if not self.rows:
            return None, None
        if not self.selected:
            active = self.app.model.active_lesson_id(self.app.active_sid()) if self.app.active_sid() else None
            ridx = next((i for i, l in enumerate(self.rows) if l["id"] == active), 0)
            return ridx, 0
        lid, col = self.selected
        ridx = next((i for i, l in enumerate(self.rows) if l["id"] == lid), 0)
        return ridx, max(0, int(col))

    def _select_indices(self, ridx, col):
        if not self.rows:
            return "break"
        ridx = max(0, min(len(self.rows) - 1, ridx))
        col = max(0, min(self._max_cols(self.app.active_sid()) - 1, col))
        lesson = self.rows[ridx]
        self.selected = (lesson["id"], col)
        self.app.set_inspector_lesson(lesson["id"])
        self._ensure_visible(ridx, col)
        self.render_body()
        return "break"

    def _key_move(self, dx, dy):
        ridx, col = self._selected_indices()
        if ridx is None:
            return "break"
        return self._select_indices(ridx + dy, col + dx)

    def _key_page(self, direction):
        ridx, col = self._selected_indices()
        if ridx is None:
            return "break"
        visible = max(1, int(max(1, self.right.winfo_height()) / self.ROW_H) - 1)
        return self._select_indices(ridx + direction * visible, col)

    def _key_home_end(self, end):
        ridx, col = self._selected_indices()
        if ridx is None:
            return "break"
        return self._select_indices((len(self.rows) - 1) if end else 0, col)

    def _key_edit(self, _event=None):
        ridx, col = self._selected_indices()
        if ridx is None or not self.rows:
            return "break"
        lesson = self.rows[ridx]
        grades = self.app.model.get_grades(self.app.active_sid(), lesson["id"])
        self.app.open_grade_modal(lesson["id"], col if col < len(grades) else None)
        return "break"

    def _ensure_visible(self, ridx, col):
        total_h = max(1, len(self.rows) * self.ROW_H)
        view_h = max(1, self.right.winfo_height())
        y1, y2 = ridx * self.ROW_H, (ridx + 1) * self.ROW_H
        top = self.right.canvasy(0)
        bottom = top + view_h
        if y1 < top:
            self._yview("moveto", y1 / total_h)
        elif y2 > bottom:
            self._yview("moveto", max(0.0, (y2 - view_h) / total_h))

        total_w = max(1, self._max_cols(self.app.active_sid()) * self.GRADE_W)
        view_w = max(1, self.right.winfo_width())
        x1, x2 = col * self.GRADE_W, (col + 1) * self.GRADE_W
        left = self.right.canvasx(0)
        right = left + view_w
        if x1 < left:
            self._xview("moveto", x1 / total_w)
        elif x2 > right:
            self._xview("moveto", max(0.0, (x2 - view_w) / total_w))

    def jump_to(self, lesson_id):
        raw = str(lesson_id or "").strip().upper()
        if raw.startswith("L") and raw[1:].isdigit():
            raw = f"L{int(raw[1:]):02d}"
        if raw not in LESSON_BY_ID:
            self.app.set_status("Lesson not found")
            return False
        visible_ids = [lesson["id"] for lesson in self._visible_rows()]
        if raw not in visible_ids:
            self.phase_filter = 0
            self.status_filter = "All"
            self.search_filter = ""
            if hasattr(self.app, "phase_segment"):
                self.app.phase_segment.set(tr("All"))
            if hasattr(self.app, "journal_status_segment"):
                self.app.journal_status_segment.set(tr("All"))
            if hasattr(self.app, "journal_search_var"):
                self.app.journal_search_var.set("")
            self.render(reset_y=True)
        ids = [lesson["id"] for lesson in self.rows]
        if raw not in ids:
            return False
        index = ids.index(raw)
        self.selected = (raw, 0)
        self.app.set_inspector_lesson(raw)
        self._ensure_visible(index, 0)
        self.render_body()
        self.after(20, lambda: self._flash_cell(index, 0))
        self.app.set_status(f"Jumped to {raw}")
        return True

    def jump_active(self):
        sid = self.app.active_sid()
        if not sid:
            return False
        active = self.app.model.active_lesson_id(sid)
        if not active:
            self.app.set_status("Curriculum complete")
            return False
        return self.jump_to(active)

    def render(self, reset_y=False):
        sid = self.app.active_sid()
        old_y = 0.0 if reset_y else (self.right.yview()[0] if self.right.yview() else 0.0)
        old_x = self.right.xview()[0] if self.right.xview() else 0.0
        self.rows = self._visible_rows()
        cols = self._max_cols(sid)
        h = max(1, len(self.rows) * self.ROW_H)
        w = max(self.GRADE_W * cols, self.GRADE_W * 8)
        self.header_left.configure(width=self.LEFT_W, height=self.HEADER_H)
        self.header_right.configure(height=self.HEADER_H)
        self.left.configure(width=self.LEFT_W, scrollregion=(0, 0, self.LEFT_W, h))
        self.right.configure(scrollregion=(0, 0, w, h))
        self.header_right.configure(scrollregion=(0, 0, w, self.HEADER_H))
        self.footer_left.configure(width=self.LEFT_W)
        self.grid_columnconfigure(0, minsize=self.LEFT_W)
        self._draw_headers(cols)
        self.render_body()
        self._draw_footer()
        self._yview("moveto", old_y)
        self._xview("moveto", old_x)
        self._update_view_info()

    def _draw_headers(self, cols):
        self.header_left.delete("all")
        self.header_right.delete("all")
        scale = min(self.zoom, 1.25)
        small = max(8, int(9 * scale))
        label = max(9, int(10 * scale))

        # Frozen-pane identity band.
        self.header_left.create_rectangle(0, 0, self.LEFT_W, self.HEADER_H, fill=PREMIUM_UI["table_header"], outline="")
        self.header_left.create_text(16, 13, text=tr("FROZEN LESSON DIRECTORY"), fill=PREMIUM_UI["cyan2"],
                                     font=(FONT_MONO, small, "bold"), anchor="w")
        self.header_left.create_text(18, self.HEADER_H - 17, text=tr("PHASE / ID"), fill=PREMIUM_UI["muted"],
                                     font=(FONT_UI, label, "bold"), anchor="w")
        self.header_left.create_text(94, self.HEADER_H - 17, text=tr("LESSON / MODULE"), fill=PREMIUM_UI["muted"],
                                     font=(FONT_UI, label, "bold"), anchor="w")
        self.header_left.create_text(self.LEFT_W - 82, self.HEADER_H - 17, text=tr("AVG"), fill=PREMIUM_UI["muted"],
                                     font=(FONT_UI, label, "bold"), anchor="e")
        self.header_left.create_text(self.LEFT_W - 18, self.HEADER_H - 17, text=tr("BASE"), fill=PREMIUM_UI["muted"],
                                     font=(FONT_UI, label, "bold"), anchor="e")
        self.header_left.create_line(0, self.HEADER_H - 1, self.LEFT_W, self.HEADER_H - 1, fill=PREMIUM_UI["line"])
        # subtle frozen divider/shadow
        self.header_left.create_line(self.LEFT_W - 1, 0, self.LEFT_W - 1, self.HEADER_H, fill="#3B526C", width=1)

        self.header_right.create_rectangle(0, 0, cols * self.GRADE_W, self.HEADER_H, fill=PREMIUM_UI["table_header"], outline="")
        self.header_right.create_text(14, 13, text=tr("ASSESSMENT HISTORY  •  HORIZONTAL SCROLL"), fill=PREMIUM_UI["muted"],
                                      font=(FONT_MONO, small, "bold"), anchor="w")
        for c in range(cols):
            x = c * self.GRADE_W
            self.header_right.create_text(
                x + self.GRADE_W / 2, self.HEADER_H - 17,
                text=f"{tr('GRADE')} {c + 1:02d}", fill=PREMIUM_UI["text2"],
                font=(FONT_MONO, small, "bold"),
            )
            self.header_right.create_line(x + self.GRADE_W - 1, 27, x + self.GRADE_W - 1,
                                          self.HEADER_H - 8, fill=PREMIUM_UI["line_soft"])
        self.header_right.create_line(0, self.HEADER_H - 1, cols * self.GRADE_W,
                                      self.HEADER_H - 1, fill=PREMIUM_UI["line"])

    def _rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill, outline=None, width=1, tags=None):
        radius = max(2, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1,
            x2, y1 + radius, x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2, x1, y2,
            x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=32, fill=fill,
                                     outline=outline or fill, width=width, tags=tags)

    def render_body(self):
        self.left.delete("all")
        self.right.delete("all")
        sid = self.app.active_sid()
        if not sid:
            self.left.create_text(24, 42, text=tr("Select or create a student"), fill=PREMIUM_UI["muted"],
                                  font=(FONT_UI, 11, "bold"), anchor="w")
            return

        cols = self._max_cols(sid)
        active_lesson = self.app.model.active_lesson_id(sid)
        scale = min(self.zoom, 1.28)
        title_font = max(9, int(11 * scale))
        meta_font = max(8, int(8.5 * scale))
        grade_font = max(12, int(16 * scale))
        cell_pad = max(7, int(12 * min(self.zoom, 1.2)))
        threshold = float(self.app.model.settings.get("probation_threshold", 8.9))

        for r, lesson in enumerate(self.rows):
            y1, y2 = r * self.ROW_H, (r + 1) * self.ROW_H
            row_bg = "#061421" if r % 2 == 0 else "#071827"
            if lesson["id"] == active_lesson:
                row_bg = "#092B48"
            selected_row = bool(self.selected and self.selected[0] == lesson["id"])
            if selected_row:
                row_bg = "#0B3557"

            self.left.create_rectangle(0, y1, self.LEFT_W, y2, fill=row_bg, outline="")
            self.right.create_rectangle(0, y1, cols * self.GRADE_W, y2, fill=row_bg, outline="")

            accent = _phase_accent(lesson["phase"])
            self.left.create_rectangle(0, y1, max(3, int(4 * scale)), y2, fill=accent, outline="")
            if lesson["id"] == active_lesson:
                self.left.create_rectangle(5, y1 + 8, 8, y2 - 8, fill=PREMIUM_UI["cyan"], outline="")

            phase_x = 18
            lesson_x = 94
            self.left.create_text(phase_x, y1 + self.ROW_H * .34, text=f"P{lesson['phase']}",
                                  fill=accent, font=(FONT_MONO, max(8, int(9 * scale)), "bold"), anchor="w")
            self.left.create_text(phase_x, y1 + self.ROW_H * .70, text=lesson["id"],
                                  fill=PREMIUM_UI["muted"], font=(FONT_MONO, max(7, int(8 * scale))), anchor="w")
            self.left.create_text(lesson_x, y1 + self.ROW_H * .35, text=localize_lesson_name(lesson["name"]),
                                  fill=PREMIUM_UI["text"], font=(FONT_UI, title_font, "bold"), anchor="w")
            meta = f"{tr(lesson['type'])}  •  {tr(lesson['phase_name'])}  •  {tr('default')} ×{lesson.get('default_assessment_weight', 1)}"
            self.left.create_text(lesson_x, y1 + self.ROW_H * .70, text=tr(meta),
                                  fill=PREMIUM_UI["muted"], font=(FONT_UI, meta_font), anchor="w")

            grades = self.app.model.get_grades(sid, lesson["id"])
            if grades:
                avg = sum(float(g.get("effective_grade", g.get("grade", 0))) for g in grades) / len(grades)
                avg_color = PREMIUM_UI["green"] if avg >= threshold else PREMIUM_UI["amber"] if avg >= 6 else PREMIUM_UI["pink"]
                self.left.create_text(self.LEFT_W - 82, y1 + self.ROW_H / 2, text=f"{avg:.1f}",
                                      fill=avg_color, font=(FONT_MONO, max(8, int(9 * scale)), "bold"), anchor="e")
            else:
                self.left.create_text(self.LEFT_W - 82, y1 + self.ROW_H / 2, text="—",
                                      fill=PREMIUM_UI["muted"], font=(FONT_MONO, max(8, int(9 * scale))), anchor="e")

            self.left.create_text(self.LEFT_W - 18, y1 + self.ROW_H / 2,
                                  text=f"{lesson['weight']:.1f}×", fill=PREMIUM_UI["text2"],
                                  font=(FONT_MONO, max(8, int(9 * scale)), "bold"), anchor="e")
            self.left.create_line(12, y2 - 1, self.LEFT_W - 10, y2 - 1, fill=PREMIUM_UI["line_soft"])
            # frozen-pane shadow remains visually anchored
            self.left.create_line(self.LEFT_W - 2, y1, self.LEFT_W - 2, y2, fill="#17344E")
            self.left.create_line(self.LEFT_W - 1, y1, self.LEFT_W - 1, y2, fill="#0E263A")

            for c in range(cols):
                x1, x2 = c * self.GRADE_W, (c + 1) * self.GRADE_W
                selected = self.selected == (lesson["id"], c)
                if selected:
                    self._rounded_rect(self.right, x1 + 5, y1 + 6, x2 - 5, y2 - 6,
                                       radius=max(8,int(11*min(self.zoom,1.2))),
                                       fill="#0B3152", outline=PREMIUM_UI["cyan"], width=1)
                self.right.create_line(x2 - 1, y1 + 9, x2 - 1, y2 - 9, fill=PREMIUM_UI["line_soft"])

                if c < len(grades):
                    entry = grades[c]
                    raw = float(entry.get("grade", 0))
                    eff = float(entry.get("effective_grade", raw))
                    color = PREMIUM_UI["green"] if eff >= threshold else PREMIUM_UI["amber"] if eff >= 6 else PREMIUM_UI["pink"]
                    top_pad = max(8, int(10 * min(self.zoom, 1.2)))
                    self._rounded_rect(
                        self.right, x1 + cell_pad, y1 + top_pad, x2 - cell_pad, y2 - top_pad,
                        radius=max(6, int(9 * min(self.zoom, 1.2))),
                        fill="#081D31", outline="#16547F", width=1,
                    )
                    self.right.create_text((x1 + x2) / 2, y1 + self.ROW_H * .40,
                                           text=_fmt_grade(raw), fill=color,
                                           font=(FONT_MONO, grade_font, "bold"))
                    mult = int(entry.get("weight_multiplier", 1))
                    footer = f"×{mult}"
                    if abs(raw - eff) > 1e-9:
                        footer += f"  {tr('eff')} {_fmt_grade(eff)}"
                    self.right.create_text((x1 + x2) / 2, y1 + self.ROW_H * .72,
                                           text=footer, fill=PREMIUM_UI["muted"],
                                           font=(FONT_MONO, max(7, int(7 * scale)), "bold"))
                    if entry.get("homework_skipped"):
                        radius = max(3, int(3 * scale))
                        cx, cy = x2 - max(16, int(20 * scale)), y1 + max(13, int(16 * scale))
                        self.right.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                               fill=PREMIUM_UI["amber"], outline="")
                elif c == len(grades):
                    # The first empty transaction cell is an explicit add target.
                    self._rounded_rect(self.right, x1 + cell_pad, y1 + max(9, int(11 * scale)),
                                       x2 - cell_pad, y2 - max(9, int(11 * scale)),
                                       radius=max(7,int(10*min(self.zoom,1.2))),
                                       fill="#06182A", outline="#174B6F", width=1)
                    self.right.create_text((x1 + x2) / 2, y1 + self.ROW_H / 2,
                                           text="＋", fill=PREMIUM_UI["cyan2"],
                                           font=(FONT_UI, max(14, int(17 * scale)), "bold"))

            self.right.create_line(0, y2 - 1, cols * self.GRADE_W, y2 - 1, fill=PREMIUM_UI["line_soft"])

    def _draw_footer(self):
        self.footer_left.delete("all")
        self.footer_left.create_rectangle(0, 0, self.LEFT_W, 24, fill="#0D1520", outline="")
        self.footer_left.create_text(12, 12, text=f"{tr('PINNED')}  •  {len(self.rows)} {tr('LESSONS')}",
                                     fill=PREMIUM_UI["muted"], font=(FONT_MONO, 7, "bold"), anchor="w")
        self.footer_left.create_line(self.LEFT_W - 1, 0, self.LEFT_W - 1, 24, fill="#30445A")

    def _update_view_info(self):
        if hasattr(self.app, "journal_visible_label"):
            cols = self._max_cols(self.app.active_sid())
            self.app.journal_visible_label.configure(text=tr(f"{len(self.rows)} rows  •  {cols} grade cols"))
        if hasattr(self.app, "journal_viewport_label"):
            x = self.right.xview()
            if x:
                pct = int(round(x[0] * 100))
                self.app.journal_viewport_label.configure(text=f"{'Г' if UI_LANGUAGE == 'ru' else 'H'} {pct:02d}%  •  {int(self.zoom*100)}%")


class AuthGateway(ctk.CTk if ctk else tk.Tk):
    """Authentication and registration gateway shown before the ERP workspace."""

    def __init__(self, auth_manager):
        if ctk is None:
            raise RuntimeError("CustomTkinter is required for the authentication gateway.")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()
        apply_app_icon(self)
        self.auth = auth_manager
        set_ui_language(self.auth.model.settings.get("language", "ru"))
        self.result = None
        self.title(f"{APP_TITLE} • {tr("Sign in")}")
        self.geometry("1120x720")
        self.minsize(980, 640)
        self.configure(fg_color=PREMIUM_UI["bg"])
        self.protocol("WM_DELETE_WINDOW", self._close)
        # Registration is always available from the first launch. Nobody is
        # implicitly promoted to administrator just because the installation is new.
        self.mode = "login" if self.auth.has_admin() else "register"
        self._admin_setup_mode = False
        self._build()

    def _font(self, size, weight="normal", family=None):
        # Slightly larger typography than the old dense layout.  It matches the
        # reference proportions and prevents the 2K/Retina build from looking tiny.
        scaled = max(7, int(round(float(size) * 1.10)))
        return ctk.CTkFont(family=family or FONT_UI, size=scaled, weight=weight)

    def _build(self):
        self.grid_columnconfigure(0, weight=5)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, corner_radius=0, fg_color=PREMIUM_UI["bg"])
        left.grid(row=0, column=0, sticky="nsew")
        self.auth_left_backdrop = SmoothBackdrop(left, "overview")
        self.auth_left_backdrop.place(x=0,y=0,relwidth=1,relheight=1); self.auth_left_backdrop.lower_widget()
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        accent = ctk.CTkFrame(left, width=5, corner_radius=3, fg_color=PREMIUM_UI["cyan"])
        accent.grid(row=0, column=0, sticky="nw", padx=42, pady=(52, 0), ipady=22)
        brand = ctk.CTkFrame(left, fg_color="transparent")
        brand.grid(row=1, column=0, sticky="nw", padx=42, pady=(26, 0))
        ctk.CTkLabel(brand, text="APEX CREATOR ACADEMY", text_color=PREMIUM_UI["cyan"], font=self._font(12, "bold", FONT_MONO)).pack(anchor="w")
        ctk.CTkLabel(brand, text="ACA Platform", text_color=PREMIUM_UI["text"], font=self._font(34, "bold")).pack(anchor="w", pady=(6, 8))
        ctk.CTkLabel(
            brand,
            text="Secure academy workspace for students, instructors,\nand principal administration.",
            text_color=PREMIUM_UI["muted"], font=self._font(13), justify="left"
        ).pack(anchor="w")

        feature = ctk.CTkFrame(left, corner_radius=24, fg_color="#071522", border_width=1, border_color=PREMIUM_UI["card_border_soft"])
        feature.grid(row=3, column=0, sticky="sew", padx=42, pady=(0, 42))
        for title, text, color in [
            ("STUDENT", "Private profile, GPA, lessons and submissions", PREMIUM_UI["green"]),
            ("TEACHER", "Invite-only access with phase-level grading rights", PREMIUM_UI["violet"]),
            ("ADMIN", "Full academy control, accounts, access and backups", PREMIUM_UI["cyan"]),
        ]:
            row = ctk.CTkFrame(feature, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=10)
            ctk.CTkFrame(row, width=4, height=34, corner_radius=3, fg_color=color).pack(side="left", padx=(0, 12))
            text_box = ctk.CTkFrame(row, fg_color="transparent")
            text_box.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text_box, text=title, text_color=color, font=self._font(9, "bold", FONT_MONO)).pack(anchor="w")
            ctk.CTkLabel(text_box, text=text, text_color=PREMIUM_UI["text2"], font=self._font(10)).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(self, corner_radius=0, fg_color=PREMIUM_UI["bg"])
        right.grid(row=0, column=1, sticky="nsew")
        self.auth_right_backdrop = SmoothBackdrop(right, "journal")
        self.auth_right_backdrop.place(x=0,y=0,relwidth=1,relheight=1); self.auth_right_backdrop.lower_widget()
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.card = ctk.CTkFrame(right, width=430, corner_radius=28, fg_color=PREMIUM_UI["surface"], border_width=1, border_color=PREMIUM_UI["card_border_soft"])
        self.card.grid(row=0, column=0, padx=44, pady=44, sticky="nsew")
        self.card.grid_propagate(False)

        language_row = ctk.CTkFrame(self.card, fg_color="transparent")
        language_row.pack(fill="x", padx=26, pady=(22, 0))
        ctk.CTkLabel(
            language_row, text=tr("Language"), text_color=PREMIUM_UI["muted"],
            font=self._font(8, "bold", FONT_MONO)
        ).pack(side="left")
        self.gateway_language_segment = ctk.CTkSegmentedButton(
            language_row, values=["RU", "EN"], width=116, height=32, corner_radius=11,
            fg_color=PREMIUM_UI["surface2"], selected_color=PREMIUM_UI["surface4"],
            selected_hover_color=PREMIUM_UI["hover"], unselected_color=PREMIUM_UI["surface2"],
            unselected_hover_color=PREMIUM_UI["hover"], font=self._font(8, "bold", FONT_MONO),
            command=self._change_language,
        )
        self.gateway_language_segment.pack(side="right")
        self.gateway_language_segment.set(language_selector_value())
        self.gateway_language_badge = ctk.CTkLabel(
            language_row, text=language_display_value(), text_color=PREMIUM_UI["text2"],
            fg_color=PREMIUM_UI["surface2"], corner_radius=11, height=32, padx=10,
            font=self._font(9, "bold")
        )
        self.gateway_language_badge.pack(side="right", padx=(0, 8))
        attach_tooltip(self.gateway_language_segment, "login_language")
        attach_tooltip(self.gateway_language_badge, "language_badge")

        self.mode_segment = ctk.CTkSegmentedButton(
            self.card, values=[tr("Sign in"), tr("Create account")], height=42, corner_radius=13,
            fg_color=PREMIUM_UI["surface2"], selected_color=PREMIUM_UI["cyan2"],
            selected_hover_color="#30BFFF", unselected_color=PREMIUM_UI["surface2"],
            unselected_hover_color=PREMIUM_UI["hover"], font=self._font(10, "bold"),
            command=self._switch_mode,
        )
        self.mode_segment.pack(fill="x", padx=26, pady=(14, 18))
        self.mode_segment.set(tr("Sign in") if self.mode == "login" else tr("Create account"))
        attach_tooltip(self.mode_segment, "auth_mode")

        self.form_host = ctk.CTkFrame(self.card, fg_color="transparent")
        self.form_host.pack(fill="both", expand=True, padx=26, pady=(0, 26))
        self._render_form()
        localize_widget_tree(self)

    def _change_language(self, value):
        language = language_code_from_ui(value)
        if language == UI_LANGUAGE:
            return
        self.auth.model.settings["language"] = language
        self.auth.store.save()
        set_ui_language(language)
        self.title(f"{APP_TITLE} • {tr('Sign in')}")
        # Rebuild from canonical English literals; RU translation is then applied
        # on top. This makes RU -> EN fully reversible without stale strings.
        for child in list(self.winfo_children()):
            child.destroy()
        self._build()

    def _clear_form(self):
        for child in self.form_host.winfo_children():
            child.destroy()

    def _switch_mode(self, value):
        self._admin_setup_mode = False
        self.mode = "login" if value == tr("Sign in") else "register"
        self._render_form()

    def _entry(self, parent, label, placeholder="", show=None):
        ctk.CTkLabel(parent, text=label, text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", pady=(10, 5))
        entry = ctk.CTkEntry(parent, height=43, corner_radius=12, fg_color=PREMIUM_UI["surface2"], border_width=1, border_color="#16486F", placeholder_text=placeholder, font=self._font(11), show=show)
        entry.pack(fill="x")
        return entry

    def _render_form(self):
        self._clear_form()
        if self._admin_setup_mode:
            self._render_admin_setup()
        elif self.mode == "recover":
            self._render_recovery()
        elif self.mode == "login":
            self._render_login()
        else:
            self._render_register()
        localize_widget_tree(self.form_host)

    def _render_login(self):
        ctk.CTkLabel(self.form_host, text="Welcome back", text_color=PREMIUM_UI["text"], font=self._font(24, "bold")).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(self.form_host, text="Sign in to continue to your academy workspace.", text_color=PREMIUM_UI["muted"], font=self._font(10)).pack(anchor="w", pady=(0, 12))
        self.login_user = self._entry(self.form_host, "USERNAME", "username")
        self.login_password = self._entry(self.form_host, "PASSWORD", "••••••••", show="•")
        self.login_password.bind("<Return>", lambda _e: self._do_login())
        self.login_status = ctk.CTkLabel(self.form_host, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=340, justify="left")
        self.login_status.pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(
            self.form_host, text="Sign in", height=44, corner_radius=12,
            fg_color=PREMIUM_UI["cyan2"], hover_color="#30BFFF", text_color="#071018",
            font=self._font(11, "bold"), command=self._do_login
        ).pack(fill="x", pady=(18, 8))
        self.forgot_password_button = ctk.CTkButton(
            self.form_host, text="Forgot password?", height=34, corner_radius=10,
            fg_color="transparent", hover_color=PREMIUM_UI["hover"], text_color=PREMIUM_UI["cyan"],
            font=self._font(9, "bold"), command=self._open_recovery
        )
        self.forgot_password_button.pack(fill="x", pady=(0, 4))
        attach_tooltip(self.forgot_password_button, "forgot_password")
        self.login_user.focus_set()

    def _open_recovery(self):
        self._admin_setup_mode = False
        self.mode = "recover"
        self._recover_method = getattr(self, "_recover_method", "Recovery code")
        self._render_form()

    def _render_recovery(self):
        ctk.CTkLabel(self.form_host, text="Recover password", text_color=PREMIUM_UI["text"], font=self._font(23, "bold")).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(
            self.form_host,
            text="Use your private recovery code or the security question configured for your account.",
            text_color=PREMIUM_UI["muted"], font=self._font(10), wraplength=350, justify="left"
        ).pack(anchor="w", pady=(0, 10))

        methods = [tr("Recovery code"), tr("Security question")]
        method_internal = getattr(self, "_recover_method", "Recovery code")
        method = tr(method_internal)
        if method not in methods:
            method_internal = "Recovery code"
            method = tr("Recovery code")
        self._recover_method = method
        selector = ctk.CTkSegmentedButton(
            self.form_host, values=methods, height=34, corner_radius=10,
            fg_color=PREMIUM_UI["surface2"], selected_color=PREMIUM_UI["surface4"],
            selected_hover_color=PREMIUM_UI["hover"], unselected_color=PREMIUM_UI["surface2"],
            unselected_hover_color=PREMIUM_UI["hover"], font=self._font(9, "bold"),
            command=self._switch_recovery_method,
        )
        selector.set(method)
        selector.pack(fill="x", pady=(2, 8))
        attach_tooltip(selector, "recovery_method")

        self.recover_user = self._entry(self.form_host, "USERNAME", "username")
        self.recover_code = None
        self.recover_answer = None
        self.recover_question_label = None

        if method_internal == "Security question":
            qbox = ctk.CTkFrame(self.form_host, corner_radius=11, fg_color=PREMIUM_UI["surface2"], border_width=1, border_color=PREMIUM_UI["line_soft"])
            qbox.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(qbox, text="SECURITY QUESTION", text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=12, pady=(10, 3))
            self.recover_question_label = ctk.CTkLabel(qbox, text="Enter username, then load the question.", text_color=PREMIUM_UI["text2"], font=self._font(10, "bold"), wraplength=315, justify="left")
            self.recover_question_label.pack(anchor="w", padx=12, pady=(0, 8))
            ctk.CTkButton(qbox, text="Load question", height=32, corner_radius=10, fg_color=PREMIUM_UI["surface3"], hover_color=PREMIUM_UI["hover"], font=self._font(8, "bold"), command=self._load_security_question).pack(anchor="w", padx=12, pady=(0, 10))
            self.recover_answer = self._entry(self.form_host, "ANSWER", "Security answer", show="•")
        else:
            self.recover_code = self._entry(self.form_host, "RECOVERY CODE", "ACA-REC-XXXX-XXXX")

        self.recover_password = self._entry(self.form_host, "NEW PASSWORD", "At least 8 characters", show="•")
        self.recover_confirm = self._entry(self.form_host, "CONFIRM NEW PASSWORD", "Repeat password", show="•")
        self.recover_confirm.bind("<Return>", lambda _e: self._do_recovery())
        self.recover_status = ctk.CTkLabel(self.form_host, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=340, justify="left")
        self.recover_status.pack(anchor="w", pady=(8, 0))
        buttons = ctk.CTkFrame(self.form_host, fg_color="transparent")
        buttons.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            buttons, text="Back", width=86, height=42, corner_radius=11,
            fg_color=PREMIUM_UI["surface3"], hover_color=PREMIUM_UI["hover"],
            font=self._font(10, "bold"), command=self._back_to_login
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text="Reset password", height=42, corner_radius=11,
            fg_color=PREMIUM_UI["green2"], hover_color=PREMIUM_UI["green"], text_color="#07150F",
            font=self._font(10, "bold"), command=self._do_recovery
        ).pack(side="right", fill="x", expand=True, padx=(8, 0))
        self.recover_user.focus_set()

    def _switch_recovery_method(self, value):
        self._recover_method = "Security question" if value == tr("Security question") else "Recovery code"
        self._render_recovery()

    def _load_security_question(self):
        question = self.auth.get_security_question(self.recover_user.get())
        if self.recover_question_label is None:
            return
        if question:
            self.recover_question_label.configure(text=question, text_color=PREMIUM_UI["cyan"])
        else:
            self.recover_question_label.configure(text=tr("Security question is unavailable for this account."), text_color=PREMIUM_UI["pink"])

    def _back_to_login(self):
        self.mode = "login"
        self.mode_segment.set(tr("Sign in"))
        self._render_form()

    def _show_recovery_code(self, code, title="Recovery code"):
        if not code:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(code)
        except Exception:
            pass
        messagebox.showinfo(
            title,
            f"Save this recovery code somewhere private:\n\n{code}\n\nIt has been copied to the clipboard. The code is not stored in readable form and will not be shown again. It is replaced after each password recovery or password change.",
            parent=self,
        )

    def _do_recovery(self):
        try:
            password = self.recover_password.get()
            if password != self.recover_confirm.get():
                raise ValueError("Passwords do not match.")
            if getattr(self, "_recover_method", "Recovery code") == "Security question":
                result = self.auth.recover_password_with_security_answer(
                    self.recover_user.get(),
                    self.recover_answer.get() if self.recover_answer is not None else "",
                    password,
                )
            else:
                result = self.auth.recover_password(
                    self.recover_user.get(),
                    self.recover_code.get() if self.recover_code is not None else "",
                    password,
                )
        except Exception as exc:
            self.recover_status.configure(text=tr_error(exc))
            return
        self._show_recovery_code(result.get("recovery_code_once"), "Password recovered")
        self.mode = "login"
        self.mode_segment.set(tr("Sign in"))
        self._render_form()

    def _render_register(self):
        ctk.CTkLabel(self.form_host, text="Create an account", text_color=PREMIUM_UI["text"], font=self._font(23, "bold")).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(
            self.form_host,
            text="Student registration is open. Teacher registration requires a one-time invite code.",
            text_color=PREMIUM_UI["muted"], font=self._font(10), wraplength=350, justify="left"
        ).pack(anchor="w", pady=(0, 10))

        roles = [tr("Student"), tr("Teacher")]
        self.reg_role = ctk.CTkSegmentedButton(
            self.form_host, values=roles, height=36, corner_radius=10,
            fg_color=PREMIUM_UI["surface2"], selected_color=PREMIUM_UI["surface4"],
            selected_hover_color=PREMIUM_UI["hover"], unselected_color=PREMIUM_UI["surface2"],
            unselected_hover_color=PREMIUM_UI["hover"], font=self._font(9, "bold")
        )
        default_role = getattr(self, "_reg_role_value", "Student")
        if default_role not in ("Student", "Teacher"):
            default_role = "Student"
        self._reg_role_value = default_role
        self.reg_role.set(tr(default_role))
        self.reg_role.pack(fill="x", pady=(4, 8))

        def role_changed(value):
            self._reg_role_value = "Teacher" if value == tr("Teacher") else "Student"
            self._render_register()
        self.reg_role.configure(command=role_changed)

        self.reg_display = self._entry(self.form_host, "DISPLAY NAME", "Name shown inside ACA Platform")
        self.reg_user = self._entry(self.form_host, "USERNAME", "3–32 characters")
        role = self._reg_role_value
        self.reg_age = None
        self.reg_invite = None
        if role == "Student":
            self.reg_age = self._entry(self.form_host, "AGE", "0")
        else:
            self.reg_invite = self._entry(self.form_host, "TEACHER INVITE CODE", "ACA-TEACH-XXXX")
        self.reg_password = self._entry(self.form_host, "PASSWORD", "At least 8 characters", show="•")
        self.reg_confirm = self._entry(self.form_host, "CONFIRM PASSWORD", "Repeat password", show="•")
        self.reg_confirm.bind("<Return>", lambda _e: self._do_register())
        self.reg_status = ctk.CTkLabel(self.form_host, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=340, justify="left")
        self.reg_status.pack(anchor="w", pady=(8, 0))
        ctk.CTkButton(
            self.form_host, text="Create account", height=44, corner_radius=12,
            fg_color=PREMIUM_UI["green2"], hover_color=PREMIUM_UI["green"], text_color="#07150F",
            font=self._font(11, "bold"), command=self._do_register
        ).pack(fill="x", pady=(14, 0))

        if not self.auth.has_admin():
            separator = ctk.CTkFrame(self.form_host, height=1, fg_color=PREMIUM_UI["line_soft"])
            separator.pack(fill="x", pady=(18, 12))
            ctk.CTkLabel(
                self.form_host, text="INSTALLATION OWNER", text_color=PREMIUM_UI["muted"],
                font=self._font(8, "bold", FONT_MONO)
            ).pack(anchor="w")
            ctk.CTkLabel(
                self.form_host,
                text="Principal Admin is created separately and only once. Normal registration never grants administrator rights.",
                text_color=PREMIUM_UI["muted"], font=self._font(9), wraplength=350, justify="left"
            ).pack(anchor="w", pady=(4, 8))
            ctk.CTkButton(
                self.form_host, text="Principal setup", height=36, corner_radius=10,
                fg_color="transparent", border_width=1, border_color=PREMIUM_UI["cyan2"],
                hover_color=PREMIUM_UI["hover"], text_color=PREMIUM_UI["cyan"],
                font=self._font(9, "bold"), command=self._open_admin_setup
            ).pack(fill="x")
        self.reg_display.focus_set()

    def _open_admin_setup(self):
        if self.auth.has_admin():
            self._admin_setup_mode = False
            self.mode = "login"
            self.mode_segment.set(tr("Sign in"))
            self._render_form()
            return
        self._admin_setup_mode = True
        self._render_form()

    def _render_admin_setup(self):
        if self.auth.has_admin():
            self._admin_setup_mode = False
            self.mode = "login"
            self.mode_segment.set(tr("Sign in"))
            self._render_form()
            return
        ctk.CTkLabel(self.form_host, text="Principal setup", text_color=PREMIUM_UI["text"], font=self._font(23, "bold")).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(
            self.form_host,
            text="One-time installation owner account. This path is separate from Student and Teacher registration.",
            text_color=PREMIUM_UI["muted"], font=self._font(10), wraplength=350, justify="left"
        ).pack(anchor="w", pady=(0, 10))
        warning = ctk.CTkFrame(self.form_host, corner_radius=12, fg_color="#251A14", border_width=1, border_color="#5A3B29")
        warning.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(
            warning, text="ADMIN ACCESS", text_color=PREMIUM_UI["amber"], font=self._font(8, "bold", FONT_MONO)
        ).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            warning, text="Creates the only self-bootstrapped Principal Admin. Type PRINCIPAL below to confirm.",
            text_color=PREMIUM_UI["text2"], font=self._font(9), wraplength=320, justify="left"
        ).pack(anchor="w", padx=12, pady=(0, 10))
        self.admin_display = self._entry(self.form_host, "DISPLAY NAME", "Principal name")
        self.admin_user = self._entry(self.form_host, "USERNAME", "admin username")
        self.admin_password = self._entry(self.form_host, "PASSWORD", "At least 8 characters", show="•")
        self.admin_confirm = self._entry(self.form_host, "CONFIRM PASSWORD", "Repeat password", show="•")
        self.admin_phrase = self._entry(self.form_host, "SETUP CONFIRMATION", "Type PRINCIPAL")
        self.admin_phrase.bind("<Return>", lambda _e: self._do_admin_setup())
        self.admin_status = ctk.CTkLabel(self.form_host, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=340, justify="left")
        self.admin_status.pack(anchor="w", pady=(8, 0))
        buttons = ctk.CTkFrame(self.form_host, fg_color="transparent")
        buttons.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            buttons, text="Back", width=86, height=42, corner_radius=11, fg_color=PREMIUM_UI["surface3"],
            hover_color=PREMIUM_UI["hover"], font=self._font(10, "bold"), command=self._close_admin_setup
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text="Create Principal Admin", height=42, corner_radius=11,
            fg_color=PREMIUM_UI["cyan2"], hover_color="#30BFFF", text_color="#071018",
            font=self._font(10, "bold"), command=self._do_admin_setup
        ).pack(side="right", fill="x", expand=True, padx=(8, 0))
        self.admin_display.focus_set()

    def _close_admin_setup(self):
        self._admin_setup_mode = False
        self.mode = "register"
        self.mode_segment.set(tr("Create account"))
        self._render_form()

    def _do_admin_setup(self):
        try:
            if self.auth.has_admin():
                raise PermissionError("Principal Admin already exists.")
            if self.admin_phrase.get().strip().upper() != "PRINCIPAL":
                raise ValueError("Type PRINCIPAL in the setup confirmation field.")
            password = self.admin_password.get()
            if password != self.admin_confirm.get():
                raise ValueError("Passwords do not match.")
            account = self.auth.register_admin(
                self.admin_user.get(), password, self.admin_display.get(), bootstrap=True
            )
            recovery_code = account.get("recovery_code_once")
            context = self.auth.login(account["username"], password)
        except Exception as exc:
            self.admin_status.configure(text=tr_error(exc))
            return
        self._show_recovery_code(recovery_code, "Principal recovery code")
        self.result = context
        self.destroy()

    def _do_login(self):
        try:
            password = self.login_password.get()
            context = self.auth.login(self.login_user.get(), password)
        except Exception as exc:
            self.login_status.configure(text=tr_error(exc))
            return
        if context.get("must_change_password"):
            self._forced_context = context
            self._forced_current_password = password
            self._render_forced_password_change()
            return
        self._show_recovery_code(context.get("recovery_code_once"), "Your recovery code")
        self.result = context
        self.destroy()

    def _render_forced_password_change(self):
        self._clear_form()
        ctk.CTkLabel(self.form_host, text="Password reset required", text_color=PREMIUM_UI["text"], font=self._font(23, "bold")).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(
            self.form_host,
            text="An administrator reset this account password. Choose a new private password before entering ACA Platform.",
            text_color=PREMIUM_UI["muted"], font=self._font(10), wraplength=350, justify="left"
        ).pack(anchor="w", pady=(0, 12))
        self.force_password = self._entry(self.form_host, "NEW PASSWORD", "At least 8 characters", show="•")
        self.force_confirm = self._entry(self.form_host, "CONFIRM NEW PASSWORD", "Repeat password", show="•")
        self.force_confirm.bind("<Return>", lambda _e: self._do_forced_password_change())
        self.force_status = ctk.CTkLabel(self.form_host, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=340, justify="left")
        self.force_status.pack(anchor="w", pady=(8, 0))
        ctk.CTkButton(
            self.form_host, text="Save new password", height=44, corner_radius=12,
            fg_color=PREMIUM_UI["cyan2"], hover_color="#30BFFF", text_color="#071018",
            font=self._font(11, "bold"), command=self._do_forced_password_change
        ).pack(fill="x", pady=(18, 8))
        self.force_password.focus_set()

    def _do_forced_password_change(self):
        try:
            new_password = self.force_password.get()
            if new_password != self.force_confirm.get():
                raise ValueError("Passwords do not match.")
            context = self._forced_context
            result = self.auth.complete_forced_password_change(
                context.get("user_id"), self._forced_current_password, new_password
            )
            context = self.auth.login(context.get("username"), new_password)
        except Exception as exc:
            self.force_status.configure(text=tr_error(exc))
            return
        self._show_recovery_code(result.get("recovery_code_once"), "New recovery code")
        self.result = context
        self.destroy()

    def _do_register(self):
        try:
            password = self.reg_password.get()
            if password != self.reg_confirm.get():
                raise ValueError("Passwords do not match.")
            role = self._reg_role_value
            if role == "Teacher":
                account = self.auth.register_teacher(self.reg_invite.get(), self.reg_user.get(), password, self.reg_display.get())
            else:
                account = self.auth.register_student(self.reg_user.get(), password, self.reg_display.get(), self.reg_age.get() or 0)
            recovery_code = account.get("recovery_code_once")
            context = self.auth.login(account["username"], password)
        except Exception as exc:
            self.reg_status.configure(text=tr_error(exc))
            return
        self._show_recovery_code(recovery_code, "Your recovery code")
        self.result = context
        self.destroy()

    def _close(self):
        self.result = None
        self.destroy()


class AcademyApp(ctk.CTk if ctk else tk.Tk):
    def __init__(self, model, auth_context, auth_manager):
        if ctk is None:
            raise RuntimeError("CustomTkinter is required. Install it with: python3 -m pip install customtkinter pillow")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()
        apply_app_icon(self)
        self.model = model
        set_ui_language(self.model.settings.get("language", "ru"))
        self.auth_context = dict(auth_context or {})
        self.auth_manager = auth_manager
        self.analytics_engine = StudentPerformanceAnalytics(model)
        self.teacher_manager = getattr(auth_manager, "teacher_manager", None) or TeacherOnboardingManager(model.store)
        self.logout_requested = False
        if self.auth_context.get("role") == "STUDENT":
            self._active_student_id = self.auth_context.get("student_id")
        else:
            preferred = self.model.settings.get("active_student_id")
            self._active_student_id = preferred if preferred in self.model.students else next(iter(self.model.students), None)
        self.title(f"{APP_TITLE}  •  {APP_VERSION}")
        self.geometry("1540x960")
        self.minsize(1280, 780)
        self.configure(fg_color=PREMIUM_UI["bg"])
        self.current_page = None
        self.nav_buttons = {}
        self.pages = {}
        self._icon_cache = {}
        self._brand_images = {}
        self.status_var = tk.StringVar(value="Ready")
        self.student_label_to_id = {}
        self.inspector_lesson_id = None
        self._live_sync_state = "ONLINE"
        self._live_sync_failures = 0
        self._live_sync_failure_started = None
        self._live_sync_last_success = None
        self._live_sync_syncing_until = 0.0
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_shell()
        self.refresh_all()
        self._set_live_sync_state("ONLINE", touch_time=True)
        self._live_sync_job = self.after(getattr(self.model.store, "poll_interval_ms", 120), self.live_sync_tick)

    def _font(self, size, weight="normal", family=None):
        # Slightly larger typography than the old dense layout.  It matches the
        # reference proportions and prevents the 2K/Retina build from looking tiny.
        scaled = max(7, int(round(float(size) * 1.10)))
        return ctk.CTkFont(family=family or FONT_UI, size=scaled, weight=weight)

    def _icon(self, kind, size=22, color=None, glow=True):
        color = color or PREMIUM_UI["cyan"]
        size = int(size)
        key = (kind, size, color, bool(glow))
        if key in self._icon_cache:
            return self._icon_cache[key]
        if not PIL_AVAILABLE:
            return None
        # CTkImage wants a source bitmap larger than its logical display size on
        # Retina/HiDPI screens.  Feeding it a 3x source prevents the OS/Tk layer
        # from magnifying a tiny 18-24 px bitmap and creating jagged edges.
        source_size = max(size * 3, 48)
        image = _neon_icon_pil(kind, source_size, color, glow=glow)
        icon = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
        self._icon_cache[key] = icon
        return icon

    def _brand_icon(self, size=46):
        key = int(size)
        if key in self._brand_images:
            return self._brand_images[key]
        if PIL_AVAILABLE:
            try:
                path = resource_path(APP_ICON_RESOURCE)
                img = Image.open(path).convert("RGBA")
                icon = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
                self._brand_images[key] = icon
                return icon
            except Exception:
                pass
        return self._icon("graduation", size, PREMIUM_UI["cyan"])

    def _bind_nav_hover(self, button, key):
        icon_kind = key if key != "overview" else "home"
        def enter(_e=None):
            if self.current_page != key:
                button.configure(
                    fg_color="#091D32", text_color=PREMIUM_UI["text"],
                    image=self._icon(icon_kind,24,"#63CFFF",glow=False),
                )
        def leave(_e=None):
            if self.current_page != key:
                button.configure(
                    fg_color="#040F1E", text_color=PREMIUM_UI["text2"],
                    image=self._icon(icon_kind,24,"#78A9CE",glow=False),
                )
        button.bind("<Enter>", enter, add="+")
        button.bind("<Leave>", leave, add="+")

    def _quick_add_grade(self):
        sid = self.active_sid()
        if not sid:
            return
        lesson_id = self.inspector_lesson_id or self.model.active_lesson_id(sid) or "L01"
        if lesson_id in LESSON_BY_ID:
            self.open_grade_modal(lesson_id)

    def _show_notifications(self):
        notes = list(self.model.store.data.get("notifications", []))[-8:]
        if not notes:
            messagebox.showinfo(tr("Notifications"), tr("No notifications"), parent=self)
            return
        lines = []
        for item in reversed(notes):
            when = format_relative_date_localized(item.get("created_at"))
            lines.append(f"• {tr(item.get('message',''))}\n  {when}")
        messagebox.showinfo(tr("Notifications"), "\n\n".join(lines), parent=self)

    def _refresh_topbar_badges(self):
        if hasattr(self, "notification_badge"):
            unread = sum(1 for n in self.model.store.data.get("notifications", []) if not n.get("read"))
            if unread:
                self.notification_badge.configure(text=str(min(unread, 99)))
                self.notification_badge.place(relx=.72,rely=.08,anchor="center")
            else:
                self.notification_badge.place_forget()
        if hasattr(self, "top_account_name"):
            self.top_account_name.configure(text=self.auth_context.get("display_name") or self.auth_context.get("username") or tr("Account"))
            self.top_account_role.configure(text=self.role_label())

    def _refresh_journal_chrome(self):
        if not hasattr(self, "journal_profile_name"):
            return
        sid = self.active_sid()
        if not sid:
            self.journal_profile_name.configure(text=tr("No student"))
            self.journal_profile_meta.configure(text=tr("Create a profile"))
            self.journal_profile_avatar.configure(text="—")
            self.journal_profile_skill.configure(text="—")
            for key in ("gpa", "grades", "avg"):
                self.journal_profile_metrics[key].configure(text="—")
            for p, (bar, pct) in self.journal_phase_progress.items():
                bar.set(0); pct.configure(text="0%")
            return
        student = self.model.get_student(sid)
        name = student.get("name", tr("Student"))
        self.journal_profile_name.configure(text=name)
        self.journal_profile_avatar.configure(text=(name[:1] or "?").upper())
        self.journal_profile_meta.configure(text=f"{tr('Student')}  •  {student.get('age','—')} {tr('years')}".rstrip())
        self.journal_profile_skill.configure(text=f"{tr('SKILL CLASS')}: {student.get('skill_class') or tr('Unranked')}")
        grades = self.model.total_grade_count(sid)
        gpa = self.model.weighted_gpa(sid)
        all_values=[]
        for lesson in CURRICULUM:
            all_values.extend(float(x.get("effective_grade", x.get("grade",0))) for x in self.model.get_grades(sid, lesson["id"]))
        avg = sum(all_values)/len(all_values) if all_values else 0.0
        self.journal_profile_metrics["gpa"].configure(text=f"{gpa:.2f}")
        self.journal_profile_metrics["grades"].configure(text=str(grades))
        self.journal_profile_metrics["avg"].configure(text=f"{avg:.1f}" if all_values else "—")
        if hasattr(self, "journal_track_frame"):
            for child in self.journal_track_frame.winfo_children(): child.destroy()
            for track in student.get("active_tracks") or []:
                accent = PREMIUM_UI["green"] if str(track).lower().startswith("game") else PREMIUM_UI["violet"]
                chip = ctk.CTkLabel(self.journal_track_frame, text=track_display_value(track), height=28, corner_radius=12,
                                    fg_color="#082438", text_color=accent, font=self._font(9,"bold"), padx=10)
                chip.pack(side="left", padx=(0,6))
        for p,(bar,pct) in self.journal_phase_progress.items():
            lessons=[l for l in CURRICULUM if l["phase"]==p]
            done=sum(1 for l in lessons if self.model.get_grades(sid,l["id"]))
            ratio=done/max(1,len(lessons)); bar.set(ratio); pct.configure(text=f"{ratio*100:.0f}%")
        self._refresh_journal_activity()

    def _refresh_journal_activity(self):
        if not hasattr(self, "journal_activity_box"):
            return
        for child in self.journal_activity_box.winfo_children(): child.destroy()
        sid=self.active_sid()
        records=[x for x in self.model.store.data.get("audit_log",[]) if not sid or x.get("student_id")==sid][-4:]
        action_labels={
            "GRADE_SUBMITTED":"Grade added", "GRADE_UPDATED":"Grade updated",
            "LEVEL_ID_UPDATED":"Level ID updated", "SHOWCASE_URL_UPDATED":"Showcase URL updated",
            "ACCOUNT_ROLE_CHANGED":"Account role updated", "PASSWORD_RESET_BY_ADMIN":"Password reset",
        }
        if not records:
            ctk.CTkLabel(self.journal_activity_box,text=tr("No recent activity"),text_color=PREMIUM_UI["muted"],font=self._font(9)).pack(anchor="w",padx=12,pady=12)
            return
        for item in reversed(records):
            row=ctk.CTkFrame(self.journal_activity_box,fg_color="transparent",height=30)
            row.pack(fill="x",padx=8,pady=2)
            action=tr(action_labels.get(item.get("action"), item.get("action","System").replace("_"," ").title()))
            lid=item.get("lesson_id") or ""
            dot=ctk.CTkLabel(row,text="●",width=18,text_color=PREMIUM_UI["violet"] if "SHOWCASE" in item.get("action","") else PREMIUM_UI["cyan"],font=self._font(10,"bold"))
            dot.pack(side="left")
            ctk.CTkLabel(row,text=(action + (f"  ·  {lid}" if lid else "")),text_color=PREMIUM_UI["text2"],font=self._font(9,"bold"),anchor="w").pack(side="left",fill="x",expand=True,padx=(5,8))
            ctk.CTkLabel(row,text=format_relative_date_localized(item.get("created_at")),text_color=PREMIUM_UI["muted"],font=self._font(8),anchor="e").pack(side="right")

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=238, corner_radius=0, fg_color=PREMIUM_UI["sidebar"], border_width=0)
        self.sidebar.grid(row=0,column=0,sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=PREMIUM_UI["bg"], border_width=0)
        self.main.grid(row=0,column=1,sticky="nsew")
        self.main.grid_rowconfigure(1,weight=1)
        self.main.grid_columnconfigure(0,weight=1)
        self._build_sidebar()
        self._build_topbar()
        self.page_host = ctk.CTkFrame(self.main, corner_radius=0, fg_color=PREMIUM_UI["bg"], border_width=0)
        self.page_host.grid(row=1,column=0,sticky="nsew",padx=18,pady=(12,12))
        self.page_host.grid_rowconfigure(0,weight=1); self.page_host.grid_columnconfigure(0,weight=1)
        self._build_pages()
        localize_widget_tree(self)
        self.status = ctk.CTkLabel(self.main,textvariable=self.status_var,text_color="#5F7594",font=self._font(8),anchor="w")
        self.status.grid(row=2,column=0,sticky="ew",padx=22,pady=(0,6))
        self.show_page("overview")

    def _build_sidebar(self):
        # Ambient artwork occupies the empty lower part of the navigation rail.
        self.sidebar_backdrop = SmoothBackdrop(self.sidebar, "sidebar")
        self.sidebar_backdrop.place(x=0,y=0,relwidth=1,relheight=1)
        self.sidebar_backdrop.lower_widget()
        edge = ctk.CTkFrame(self.sidebar,width=1,corner_radius=0,fg_color="#0D3153")
        edge.place(relx=1.0,y=0,relheight=1.0,anchor="ne")

        top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(18,12))
        logo_plate = ctk.CTkFrame(top,width=74,height=74,corner_radius=20,fg_color="#07172B",border_width=1,border_color="#164A78")
        logo_plate.pack(anchor="center"); logo_plate.pack_propagate(False)
        ctk.CTkLabel(logo_plate,text="",image=self._brand_icon(58),width=62,height=62).place(relx=.5,rely=.5,anchor="center")
        ctk.CTkLabel(top,text="ACA Platform",text_color=PREMIUM_UI["text"],font=self._font(16,"bold")).pack(anchor="center",pady=(9,0))

        ctk.CTkLabel(self.sidebar,text="WORKSPACE",text_color="#617895",font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=22,pady=(14,8))
        nav = [
            ("overview","Overview","home"),
            ("journal","Journal","journal"),
            ("analytics","Analytics","analytics"),
            ("graduation","Graduation","graduation"),
        ]
        if self.is_admin(): nav.append(("access","Access & Accounts","access"))
        for key,label,icon_kind in nav:
            btn=ctk.CTkButton(
                self.sidebar,text=label,image=self._icon(icon_kind,24,"#78A9CE",glow=False),compound="left",
                anchor="w",height=54,corner_radius=16,fg_color="#040F1E",hover_color="#0A223A",
                border_width=0,text_color=PREMIUM_UI["text2"],
                font=self._font(10,"bold"),command=lambda k=key:self.show_page(k)
            )
            btn.pack(fill="x",padx=12,pady=4)
            self.nav_buttons[key]=btn
            self._bind_nav_hover(btn,key)
            attach_tooltip(btn,{"overview":"nav_overview","journal":"nav_journal","analytics":"nav_analytics","graduation":"nav_graduation","access":"nav_access"}.get(key,"nav_overview"))
        self.nav_marker = None

        version_card=ctk.CTkFrame(self.sidebar,corner_radius=18,fg_color="#06152A",border_width=1,border_color="#144A78")
        version_card.place(relx=.065,rely=.892,relwidth=.87,anchor="nw")
        ctk.CTkLabel(version_card,text="",image=self._brand_icon(34),width=40,height=40).pack(side="left",padx=(10,7),pady=10)
        vb=ctk.CTkFrame(version_card,fg_color="transparent"); vb.pack(side="left",fill="x",expand=True,pady=9)
        ctk.CTkLabel(vb,text="ACA Platform",text_color=PREMIUM_UI["text"],font=self._font(9,"bold")).pack(anchor="w")
        ctk.CTkLabel(vb,text=f"{tr('Version') if 'Version' in RU_TEXT else 'Version'} {APP_VERSION}",text_color=PREMIUM_UI["muted"],font=self._font(7)).pack(anchor="w",pady=(1,0))

        # Hidden compatibility objects used by refresh_overview().
        self.sidebar_student=ctk.CTkFrame(self.sidebar,fg_color="transparent")
        self.sidebar_student_name=ctk.CTkLabel(self.sidebar_student,text="")
        self.sidebar_student_meta=ctk.CTkLabel(self.sidebar_student,text="")
        self.backup_button=ctk.CTkButton(self.sidebar,text="",command=self.backup_database)

    def _build_topbar(self):
        """Build a single-height, macOS-safe top bar without nested transparent button artifacts."""
        TOP_H = 88
        CONTROL_H = 46
        RADIUS = 15
        PILL_BG = "#07182A"
        PILL_HOVER = "#0C2742"
        PILL_BORDER = "#174A75"
        PILL_BORDER_HOVER = "#236B9F"

        bar = ctk.CTkFrame(self.main, height=TOP_H, corner_radius=0, fg_color="#030C18", border_width=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_propagate(False)
        ctk.CTkFrame(bar, height=1, corner_radius=0, fg_color="#10385E").place(
            relx=0, rely=1, relwidth=1, anchor="sw"
        )

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(20, 10), pady=11)
        ctk.CTkLabel(brand, text="", image=self._brand_icon(46), width=50, height=50).pack(
            side="left", padx=(0, 11)
        )
        bt = ctk.CTkFrame(brand, fg_color="transparent")
        bt.pack(side="left")
        ctk.CTkLabel(
            bt, text="ACA Platform", text_color=PREMIUM_UI["text"], font=self._font(22, "bold")
        ).pack(anchor="w")
        self.page_title = ctk.CTkLabel(
            bt, text="Overview", text_color="#91A8C5", font=self._font(9, "bold")
        )
        self.page_title.pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=(10, 16), pady=20)

        # Student selector: the combo button uses the SAME fill as the field so there
        # is no rectangular split at the right edge on macOS/Retina.
        self.student_combo = ctk.CTkComboBox(
            right, width=192, height=CONTROL_H, corner_radius=RADIUS,
            fg_color=PILL_BG, border_width=1, border_color=PILL_BORDER,
            button_color=PILL_BG, button_hover_color=PILL_HOVER,
            dropdown_fg_color="#071522", dropdown_hover_color="#0D2843",
            text_color=PREMIUM_UI["text"], font=self._font(9),
            command=self.on_student_combo,
        )
        self.student_combo.pack(side="left", padx=(0, 8))
        attach_tooltip(self.student_combo, "student_selector")

        self.refresh_students_button = ctk.CTkButton(
            right, text="", image=self._icon("refresh", 19, PREMIUM_UI["cyan"], glow=False),
            width=CONTROL_H, height=CONTROL_H, corner_radius=RADIUS,
            fg_color=PILL_BG, hover_color=PILL_HOVER,
            border_width=1, border_color=PILL_BORDER,
            command=self.manual_refresh_students,
        )
        self.refresh_students_button.pack(side="left", padx=(0, 10))
        attach_tooltip(self.refresh_students_button, "refresh_students")

        # Live sync is one self-contained pill. Child labels explicitly share the
        # parent fill instead of relying on transparent-background inheritance.
        live_bg = "#05231D"
        self.live_sync_badge = ctk.CTkFrame(
            right, width=154, height=CONTROL_H, corner_radius=RADIUS,
            fg_color=live_bg, border_width=1, border_color="#1E9F7C",
        )
        self.live_sync_badge.pack(side="left", padx=(0, 10))
        self.live_sync_badge.pack_propagate(False)
        self.live_sync_label = ctk.CTkLabel(
            self.live_sync_badge, text=f"● {tr('ONLINE')}",
            width=132, height=17, fg_color=live_bg, text_color=PREMIUM_UI["green"],
            font=self._font(8, "bold", FONT_MONO), anchor="w",
        )
        self.live_sync_label.place(x=11, y=6)
        self.live_sync_time_label = ctk.CTkLabel(
            self.live_sync_badge, text=tr("Last sync —"),
            width=132, height=16, fg_color=live_bg, text_color="#7893AA",
            font=self._font(7, "bold", FONT_MONO), anchor="w",
        )
        self.live_sync_time_label.place(x=11, y=24)
        for w in (self.live_sync_badge, self.live_sync_label, self.live_sync_time_label):
            attach_tooltip(w, "live_sync")

        # Language block: one rounded outer surface. No transparent child area is
        # allowed to expose a square Tk background behind the segmented control.
        lang = ctk.CTkFrame(
            right, width=270, height=CONTROL_H, corner_radius=RADIUS,
            fg_color=PILL_BG, border_width=1, border_color=PILL_BORDER,
        )
        lang.pack(side="left", padx=(0, 10))
        lang.pack_propagate(False)
        self.language_badge = ctk.CTkLabel(
            lang, text=language_display_value(), width=147, height=44,
            fg_color=PILL_BG, text_color=PREMIUM_UI["text2"],
            corner_radius=0, font=self._font(8, "bold"), anchor="w",
        )
        self.language_badge.place(x=13, y=1)
        self.language_segment = ctk.CTkSegmentedButton(
            lang, values=["RU", "EN"], width=96, height=34, corner_radius=11,
            fg_color="#061421", selected_color="#123F68",
            selected_hover_color="#195781", unselected_color="#061421",
            unselected_hover_color="#0D2B47", font=self._font(7, "bold", FONT_MONO),
            command=self.change_language,
        )
        self.language_segment.set(language_selector_value())
        self.language_segment.place(x=165, y=6)
        attach_tooltip(self.language_badge, "language_badge")
        attach_tooltip(self.language_segment, "language_switch")

        # Notification control is a single button; the badge is the only overlay.
        # This avoids Frame -> transparent Button composition seams.
        self.notification_button = ctk.CTkButton(
            right, text="", image=self._icon("bell", 20, "#C5D8EC", glow=False),
            width=CONTROL_H, height=CONTROL_H, corner_radius=RADIUS,
            fg_color=PILL_BG, hover_color=PILL_HOVER,
            border_width=1, border_color=PILL_BORDER,
            command=self._show_notifications,
        )
        self.notification_button.pack(side="left", padx=(0, 10))
        self.notification_badge = ctk.CTkLabel(
            self.notification_button, text="", width=20, height=20, corner_radius=10,
            fg_color=PREMIUM_UI["red"], text_color="white",
            font=self._font(7, "bold"),
        )
        self.notification_badge.place(relx=.78, rely=.08, anchor="center")
        attach_tooltip(self.notification_button, "live_sync")

        # Account card must NOT be a CTkButton containing labels. CustomTkinter's
        # internal button canvas clips child backgrounds differently on macOS.
        # A normal CTkFrame keeps the rounded fill intact; click bindings provide
        # the same interaction without visual seams.
        acct = ctk.CTkFrame(
            right, width=196, height=CONTROL_H, corner_radius=RADIUS,
            fg_color=PILL_BG, border_width=1, border_color=PILL_BORDER,
        )
        acct.pack(side="left", padx=(0, 8))
        acct.pack_propagate(False)
        avatar = ctk.CTkLabel(
            acct, text=(self.auth_context.get("display_name") or "A")[:1].upper(),
            width=36, height=36, corner_radius=18,
            fg_color=PREMIUM_UI["violet2"], text_color="white",
            font=self._font(12, "bold"),
        )
        avatar.place(x=8, y=5)
        self.top_account_name = ctk.CTkLabel(
            acct,
            text=self.auth_context.get("display_name") or self.auth_context.get("username") or tr("Account"),
            width=134, height=19, fg_color=PILL_BG, text_color=PREMIUM_UI["text"],
            font=self._font(9, "bold"), anchor="w",
        )
        self.top_account_name.place(x=52, y=5)
        self.top_account_role = ctk.CTkLabel(
            acct, text=self.role_label(), width=134, height=16, fg_color=PILL_BG,
            text_color=PREMIUM_UI["muted"], font=self._font(7), anchor="w",
        )
        self.top_account_role.place(x=52, y=24)

        def _account_enter(_event=None):
            if acct.winfo_exists():
                acct.configure(fg_color=PILL_HOVER, border_color=PILL_BORDER_HOVER)
                self.top_account_name.configure(fg_color=PILL_HOVER)
                self.top_account_role.configure(fg_color=PILL_HOVER)

        def _account_leave(_event=None):
            if acct.winfo_exists():
                acct.configure(fg_color=PILL_BG, border_color=PILL_BORDER)
                self.top_account_name.configure(fg_color=PILL_BG)
                self.top_account_role.configure(fg_color=PILL_BG)

        for widget in (acct, avatar, self.top_account_name, self.top_account_role):
            widget.bind("<Button-1>", lambda _e: self.open_security(), add="+")
            widget.bind("<Enter>", _account_enter, add="+")
            widget.bind("<Leave>", _account_leave, add="+")
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass
        attach_tooltip(acct, "security")

        self.logout_button = ctk.CTkButton(
            right, text="×", width=CONTROL_H, height=CONTROL_H, corner_radius=RADIUS,
            fg_color="#071522", hover_color="#2A1420",
            border_width=1, border_color="#472234",
            text_color=PREMIUM_UI["pink"], font=self._font(13, "bold"),
            command=self.logout,
        )
        self.logout_button.pack(side="left")
        attach_tooltip(self.logout_button, "logout")

    def change_language(self, value):
        language = language_code_from_ui(value)
        if language == UI_LANGUAGE:
            return
        current_page = self.current_page or "overview"
        current_lesson = self.inspector_lesson_id
        current_sync_state = self._live_sync_state
        last_sync = self._live_sync_last_success
        self.model.settings["language"] = language
        self.model.store.save()
        set_ui_language(language)

        # Rebuild the presentation layer from its canonical English source strings.
        # Model, auth context, active student and live-sync job stay intact.
        for child in list(self.winfo_children()):
            child.destroy()
        self.nav_buttons = {}
        self.pages = {}
        self.current_page = None
        self.status_var.set(tr("Ready"))
        self._build_shell()
        self.refresh_all()
        if current_lesson and current_lesson in LESSON_BY_ID:
            self.set_inspector_lesson(current_lesson)
        if current_page in self.pages:
            self.show_page(current_page)
        self._live_sync_last_success = last_sync
        self._set_live_sync_state(current_sync_state, touch_time=False)
        self.set_status(tr("Language changed"))

    def _build_pages(self):
        self.page_backdrops = {}
        for key in ("overview", "journal", "analytics", "graduation", "access"):
            frame = ctk.CTkFrame(self.page_host, corner_radius=0, fg_color=PREMIUM_UI["bg"], border_width=0)
            frame.place(x=0, y=0, relwidth=1, relheight=1)
            self.pages[key] = frame
            backdrop = SmoothBackdrop(frame, "overview" if key == "overview" else "journal" if key == "journal" else "main")
            backdrop.place(x=0,y=0,relwidth=1,relheight=1)
            backdrop.lower_widget()
            self.page_backdrops[key] = backdrop
        self._page_anim_job = None
        self._nav_anim_job = None
        self._build_overview()
        self._build_journal()
        self._build_analytics()
        self._build_graduation()
        self._build_access()

    def _hex_mix(self, a, b, t):
        a = a.lstrip("#"); b = b.lstrip("#")
        av = tuple(int(a[i:i+2], 16) for i in (0, 2, 4))
        bv = tuple(int(b[i:i+2], 16) for i in (0, 2, 4))
        cv = tuple(round(av[i] + (bv[i] - av[i]) * t) for i in range(3))
        return "#%02x%02x%02x" % cv

    def _animate_nav_marker(self, key):
        # The old 1 px travelling marker was visually harsh on Retina displays.
        # Active state is now carried by the rounded nav plate itself.
        return

    def _animate_title(self):
        if not hasattr(self, "page_title"):
            return
        steps = 6
        def step(i=0):
            t = min(1.0, (i + 1) / steps)
            self.page_title.configure(text_color=self._hex_mix(PREMIUM_UI["muted"], PREMIUM_UI["text"], t))
            if i + 1 < steps:
                self.after(16, lambda: step(i + 1))
        step()

    def show_page(self, key):
        if key == "access" and not self.is_admin():
            messagebox.showerror("Access denied", "Only the Principal Administrator can manage accounts and teacher invites.", parent=self); return
        if key not in self.pages: return
        old_key=getattr(self,"current_page",None); new_page=self.pages[key]; same_page=old_key==key; self.current_page=key
        titles={"overview":"Overview","journal":"Electronic Journal","analytics":"Quantum Analytics","graduation":"Graduation Control","access":"Access & Teachers"}
        self.page_title.configure(text=tr(titles[key])); self._animate_title()
        icon_map={"overview":"home","journal":"journal","analytics":"analytics","graduation":"graduation","access":"access"}
        for k,button in self.nav_buttons.items():
            active=k==key
            button.configure(
                fg_color="#0D5EDC" if active else "#040F1E",
                hover_color="#1572F4" if active else "#091D32",
                text_color="white" if active else PREMIUM_UI["text2"],
                image=self._icon(icon_map.get(k,"home"),24,"#8EE7FF" if active else "#78A9CE",glow=active),
            )
        self.update_idletasks(); width=max(1,self.page_host.winfo_width())
        if same_page or width<100:
            new_page.place_configure(x=0); new_page.lift()
        else:
            old_page=self.pages.get(old_key); new_page.place_configure(x=24); new_page.lift(); steps=10
            if self._page_anim_job:
                try:self.after_cancel(self._page_anim_job)
                except Exception:pass
            def animate(i=0):
                if i>=steps:
                    new_page.place_configure(x=0)
                    if old_page is not None: old_page.place_configure(x=0)
                    return
                t=(i+1)/steps; eased=1-(1-t)**3; new_page.place_configure(x=round(24*(1-eased)))
                self._page_anim_job=self.after(11,lambda:animate(i+1))
            animate()
        if key=="journal" and hasattr(self,"grade_grid"): self.grade_grid.focus_set()

    def _section_header(self,parent,title,subtitle=None):
        ctk.CTkLabel(parent,text=title,text_color=PREMIUM_UI["text"],font=self._font(18,"bold")).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(parent,text=subtitle,text_color=PREMIUM_UI["muted"],font=self._font(10)).pack(anchor="w",pady=(2,10))

    def _bind_card_hover(self, widget, target=None):
        target = target or widget
        jobs = {"job": None}
        def animate(to_color):
            if jobs["job"]:
                try:self.after_cancel(jobs["job"])
                except Exception:pass
            try:
                start=target.cget("fg_color")
                if isinstance(start,(tuple,list)): start=start[0]
                if start=="transparent": start=PREMIUM_UI["surface"]
            except Exception:
                start=PREMIUM_UI["surface"]
            steps=8
            def step(i=0):
                t=min(1.0,(i+1)/steps)
                try:target.configure(fg_color=self._hex_mix(start,to_color,t))
                except Exception:return
                if i+1<steps: jobs["job"]=self.after(14,lambda:step(i+1))
            step()
        def on_enter(_e=None):
            try:target.configure(border_color="#185B8C")
            except Exception:pass
            animate("#091A2D")
        def on_leave(_e=None):
            try:target.configure(border_color=PREMIUM_UI["card_border_soft"])
            except Exception:pass
            animate(PREMIUM_UI["surface"])
        widget.bind("<Enter>",on_enter,add="+")
        widget.bind("<Leave>",on_leave,add="+")

    def _metric_card(self,parent,title,accent):
        icon_kind = "cap" if "GPA" in title else "clipboard" if "transaction" in title.lower() else "book" if "lesson" in title.lower() else "target"
        border = self._hex_mix(PREMIUM_UI["card_border_soft"], accent, .28)
        f=ctk.CTkFrame(parent,corner_radius=21,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=border)
        accent_bar=ctk.CTkFrame(f,width=4,corner_radius=4,fg_color=accent)
        accent_bar.place(x=0,rely=.18,relheight=.64,anchor="nw")
        row=ctk.CTkFrame(f,fg_color="transparent"); row.pack(fill="both",expand=True,padx=18,pady=17)
        tile=ctk.CTkFrame(row,width=62,height=62,corner_radius=18,fg_color=self._hex_mix(PREMIUM_UI["surface2"],accent,.12),border_width=1,border_color=self._hex_mix(PREMIUM_UI["line_soft"],accent,.38))
        tile.pack(side="left",padx=(0,15)); tile.pack_propagate(False)
        ctk.CTkLabel(tile,text="",image=self._icon(icon_kind,29,accent,glow=True),width=40,height=40).place(relx=.5,rely=.5,anchor="center")
        body=ctk.CTkFrame(row,fg_color="transparent"); body.pack(side="left",fill="both",expand=True)
        ctk.CTkLabel(body,text=title.upper(),text_color="#8EA3C1",font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",pady=(2,0))
        val=ctk.CTkLabel(body,text="—",text_color=PREMIUM_UI["text"],font=self._font(23,"bold",FONT_MONO))
        val.pack(anchor="w",pady=(7,0))
        self._bind_card_hover(f); self._bind_card_hover(row,target=f); self._bind_card_hover(tile,target=f)
        return f,val

    def _build_overview(self):
        page=self.pages["overview"]; page.grid_columnconfigure(0,weight=1); page.grid_rowconfigure(2,weight=1)
        self.hero=HeroPanel(page,self,height=232); self.hero.grid(row=0,column=0,sticky="ew",pady=(0,14))

        metrics=ctk.CTkFrame(page,fg_color="transparent"); metrics.grid(row=1,column=0,sticky="ew",pady=(0,14))
        for i in range(4): metrics.grid_columnconfigure(i,weight=1)
        self.metric_values={}
        specs=[("gpa","Weighted GPA",PREMIUM_UI["cyan"]),("grades","Grade transactions",PREMIUM_UI["violet"]),("lessons","Lessons touched",PREMIUM_UI["green"]),("consistency","Consistency",PREMIUM_UI["amber"])]
        for i,(key,title,accent) in enumerate(specs):
            card,val=self._metric_card(metrics,title,accent)
            card.grid(row=0,column=i,sticky="ew",padx=(0 if i==0 else 6,0 if i==3 else 6))
            self.metric_values[key]=val

        lower=ctk.CTkFrame(page,fg_color="transparent"); lower.grid(row=2,column=0,sticky="nsew")
        lower.grid_columnconfigure(0,weight=3); lower.grid_columnconfigure(1,weight=2); lower.grid_rowconfigure(0,weight=1)

        chart_card=ctk.CTkFrame(lower,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"])
        chart_card.grid(row=0,column=0,sticky="nsew",padx=(0,8))
        chart_head=ctk.CTkFrame(chart_card,fg_color="transparent"); chart_head.pack(fill="x",padx=18,pady=(16,0))
        trend_tile=ctk.CTkFrame(chart_head,width=42,height=42,corner_radius=13,fg_color="#07233A",border_width=1,border_color="#165A8B")
        trend_tile.pack(side="left"); trend_tile.pack_propagate(False)
        ctk.CTkLabel(trend_tile,text="",image=self._icon("trend",23,PREMIUM_UI["cyan"],glow=True)).place(relx=.5,rely=.5,anchor="center")
        txt=ctk.CTkFrame(chart_head,fg_color="transparent"); txt.pack(side="left",padx=(11,0))
        ctk.CTkLabel(txt,text="GPA trajectory",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w")
        ctk.CTkLabel(txt,text="Weighted after every recorded grade",text_color=PREMIUM_UI["muted"],font=self._font(9)).pack(anchor="w",pady=(1,0))
        self.gpa_chart=GPAChart(chart_card,self); self.gpa_chart.pack(fill="both",expand=True,padx=14,pady=(6,14))
        self._bind_card_hover(chart_card)

        side=ctk.CTkFrame(lower,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"])
        side.grid(row=0,column=1,sticky="nsew",padx=(8,0))
        side_head=ctk.CTkFrame(side,fg_color="transparent"); side_head.pack(fill="x",padx=18,pady=(16,5))
        phase_tile=ctk.CTkFrame(side_head,width=42,height=42,corner_radius=13,fg_color="#07233A",border_width=1,border_color="#165A8B")
        phase_tile.pack(side="left"); phase_tile.pack_propagate(False)
        ctk.CTkLabel(phase_tile,text="",image=self._icon("analytics",23,PREMIUM_UI["cyan"],glow=True)).place(relx=.5,rely=.5,anchor="center")
        stxt=ctk.CTkFrame(side_head,fg_color="transparent"); stxt.pack(side="left",padx=(11,0))
        ctk.CTkLabel(stxt,text="Phase performance",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w")
        ctk.CTkLabel(stxt,text="Current weighted average by training block",text_color=PREMIUM_UI["muted"],font=self._font(9)).pack(anchor="w",pady=(1,0))
        self.phase_rows={}
        for p in range(1,8):
            row=ctk.CTkFrame(side,fg_color="transparent"); row.pack(fill="x",padx=18,pady=6)
            ctk.CTkLabel(row,text=f"P{p}",width=30,text_color=_phase_accent(p),font=self._font(9,"bold",FONT_MONO)).pack(side="left")
            dot=ctk.CTkLabel(row,text="●",width=14,text_color=_phase_accent(p),font=self._font(8,"bold")); dot.pack(side="left",padx=(1,5))
            bar=ctk.CTkProgressBar(row,height=9,corner_radius=8,progress_color=_phase_accent(p),fg_color="#122742")
            bar.pack(side="left",fill="x",expand=True,padx=(0,10)); bar.set(0)
            val=ctk.CTkLabel(row,text="—",width=44,text_color=PREMIUM_UI["text2"],font=self._font(9,"bold",FONT_MONO)); val.pack(side="right")
            self.phase_rows[p]=(bar,val)
        actions=ctk.CTkFrame(side,fg_color="transparent"); actions.pack(fill="x",padx=18,pady=(16,16))
        ctk.CTkButton(actions,text="Legacy import",height=38,corner_radius=12,fg_color="#0C2744",hover_color="#12385D",border_width=0,font=self._font(9,"bold"),command=self.open_legacy_import).pack(side="left")
        ctk.CTkButton(actions,text="Open journal",image=self._icon("journal",16,"#03101B",glow=False),compound="left",height=38,corner_radius=12,fg_color="#24C8F4",hover_color="#49DCFF",border_width=0,text_color="#03101B",font=self._font(9,"bold"),command=lambda:self.show_page("journal")).pack(side="right")
        self._bind_card_hover(side)

    def _build_journal(self):
        page=self.pages["journal"]
        page.grid_columnconfigure(0,weight=1); page.grid_rowconfigure(1,weight=1)

        header=ctk.CTkFrame(page,corner_radius=21,fg_color="#061522",border_width=1,border_color="#0D3E66")
        header.grid(row=0,column=0,sticky="ew",pady=(0,10)); header.grid_columnconfigure(1,weight=1)
        icon_box=ctk.CTkFrame(header,width=58,height=58,corner_radius=17,fg_color="#07243B",border_width=1,border_color="#1874A8")
        icon_box.grid(row=0,column=0,rowspan=2,padx=(14,10),pady=12); icon_box.grid_propagate(False)
        ctk.CTkLabel(icon_box,text="",image=self._icon("journal",31,PREMIUM_UI["cyan"],glow=True)).place(relx=.5,rely=.5,anchor="center")
        ctk.CTkLabel(header,text=tr("Grade journal"),text_color=PREMIUM_UI["text"],font=self._font(19,"bold")).grid(row=0,column=1,sticky="sw",pady=(13,0))
        ctk.CTkLabel(header,text=tr("Manage grades and student progress"),text_color="#9AB0CE",font=self._font(10)).grid(row=1,column=1,sticky="nw",pady=(1,12))
        self.journal_add_grade=ctk.CTkButton(header,text=tr("Add grade"),image=self._icon("plus",17,"white",glow=False),compound="left",width=148,height=42,corner_radius=13,fg_color="#147DFF",hover_color="#2D93FF",border_width=0,text_color="white",font=self._font(9,"bold"),command=self._quick_add_grade)
        self.journal_add_grade.grid(row=0,column=2,rowspan=2,padx=14,pady=15)

        content=ctk.CTkFrame(page,fg_color="transparent")
        content.grid(row=1,column=0,sticky="nsew"); content.grid_columnconfigure(0,weight=1); content.grid_columnconfigure(1,minsize=326); content.grid_rowconfigure(0,weight=1)

        left=ctk.CTkFrame(content,fg_color="transparent")
        left.grid(row=0,column=0,sticky="nsew",padx=(0,7)); left.grid_columnconfigure(0,weight=1); left.grid_rowconfigure(1,weight=1)

        toolbar=ctk.CTkFrame(left,corner_radius=18,fg_color="#071522",border_width=1,border_color=PREMIUM_UI["card_border_soft"])
        toolbar.grid(row=0,column=0,sticky="ew",pady=(0,8)); toolbar.grid_columnconfigure(1,weight=1)
        self.journal_search_var=tk.StringVar(value="")
        self.journal_search_entry=ctk.CTkEntry(toolbar,textvariable=self.journal_search_var,height=40,corner_radius=12,fg_color="#071827",border_width=1,border_color="#17496F",placeholder_text=tr("Search lessons, grades, notes…"),font=self._font(9))
        self.journal_search_entry.grid(row=0,column=0,sticky="ew",padx=(10,5),pady=9); toolbar.grid_columnconfigure(0,weight=1)
        self.journal_search_entry.bind("<KeyRelease>",self.on_journal_search); attach_tooltip(self.journal_search_entry,"journal_search")

        self.journal_status_segment=ctk.CTkSegmentedButton(toolbar,values=[tr("All"),tr("Graded"),tr("Active"),tr("Empty"),tr("At risk")],width=300,height=38,corner_radius=11,fg_color="#091A2C",selected_color="#155EC6",selected_hover_color="#1D70DA",unselected_color="#091A2C",unselected_hover_color="#0D2944",font=self._font(8,"bold"),command=self.on_journal_status)
        self.journal_status_segment.set(tr("All")); self.journal_status_segment.grid(row=0,column=1,padx=5,pady=9); attach_tooltip(self.journal_status_segment,"journal_status")
        self.phase_segment=ctk.CTkSegmentedButton(toolbar,values=[tr("All")]+[f"P{i}" for i in range(1,8)],height=38,corner_radius=11,fg_color="#091A2C",selected_color="#6846E9",selected_hover_color="#7A5AF4",unselected_color="#091A2C",unselected_hover_color="#0D2944",font=self._font(8,"bold"),command=self.on_phase_filter)
        self.phase_segment.set(tr("All")); self.phase_segment.grid(row=0,column=2,padx=(5,10),pady=9); attach_tooltip(self.phase_segment,"journal_phase")

        subbar=ctk.CTkFrame(toolbar,fg_color="transparent")
        subbar.grid(row=1,column=0,columnspan=3,sticky="ew",padx=10,pady=(0,8)); subbar.grid_columnconfigure(8,weight=1)
        self.journal_jump_var=tk.StringVar(value="")
        jump=ctk.CTkEntry(subbar,textvariable=self.journal_jump_var,width=76,height=32,corner_radius=10,fg_color="#071827",border_width=1,border_color="#17496F",placeholder_text="L01",font=self._font(8,"bold",FONT_MONO)); jump.grid(row=0,column=0,padx=(0,4)); jump.bind("<Return>",lambda _e:self.on_journal_jump()); attach_tooltip(jump,"journal_jump")
        self.journal_go_button=ctk.CTkButton(subbar,text="Go",width=44,height=32,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(8,"bold"),command=self.on_journal_jump); self.journal_go_button.grid(row=0,column=1,padx=(0,7)); attach_tooltip(self.journal_go_button,"journal_jump")
        self.journal_active_button=ctk.CTkButton(subbar,text=tr("Active"),width=68,height=32,corner_radius=10,fg_color="#0A2B49",hover_color="#104668",text_color=PREMIUM_UI["cyan"],font=self._font(8,"bold"),command=self.on_journal_active); self.journal_active_button.grid(row=0,column=2,padx=(0,10)); attach_tooltip(self.journal_active_button,"journal_active")
        self.journal_density_segment=ctk.CTkSegmentedButton(subbar,values=[tr("Compact"),tr("Comfort"),tr("Spacious")],width=214,height=32,corner_radius=10,fg_color="#091A2C",selected_color="#143D65",selected_hover_color="#1A537F",unselected_color="#091A2C",unselected_hover_color="#0D2944",font=self._font(7,"bold"),command=self.on_journal_density); self.journal_density_segment.set(tr("Comfort")); self.journal_density_segment.grid(row=0,column=3,padx=(0,8)); attach_tooltip(self.journal_density_segment,"journal_density")
        self.journal_zoom_slider=ctk.CTkSlider(subbar,from_=75,to=150,number_of_steps=75,width=130,height=14,fg_color="#102A49",progress_color=PREMIUM_UI["cyan2"],button_color=PREMIUM_UI["text"],button_hover_color=PREMIUM_UI["cyan"],command=self.on_journal_zoom); self.journal_zoom_slider.set(100); self.journal_zoom_slider.grid(row=0,column=4,padx=(0,5)); attach_tooltip(self.journal_zoom_slider,"journal_zoom")
        self.journal_zoom_value=ctk.CTkLabel(subbar,text="100%",width=40,text_color=PREMIUM_UI["text2"],font=self._font(7,"bold",FONT_MONO)); self.journal_zoom_value.grid(row=0,column=5)
        self.journal_fit_button=ctk.CTkButton(subbar,text="Fit",width=42,height=30,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(7,"bold"),command=lambda:self.grade_grid.fit_zoom()); self.journal_fit_button.grid(row=0,column=6,padx=(5,3)); attach_tooltip(self.journal_fit_button,"journal_fit")
        self.journal_reset_button=ctk.CTkButton(subbar,text="Reset",width=52,height=30,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(7,"bold"),command=lambda:self.grade_grid.reset_view()); self.journal_reset_button.grid(row=0,column=7,padx=(0,7)); attach_tooltip(self.journal_reset_button,"journal_reset")
        self.journal_visible_label=ctk.CTkLabel(subbar,text="120 rows  •  8 grade cols",text_color=PREMIUM_UI["muted"],font=self._font(7,"bold",FONT_MONO)); self.journal_visible_label.grid(row=0,column=8,sticky="e",padx=(6,7))
        self.journal_viewport_label=ctk.CTkLabel(subbar,text="H 00%  •  100%",text_color=PREMIUM_UI["muted"],font=self._font(7,"bold",FONT_MONO)); self.journal_viewport_label.grid(row=0,column=9,sticky="e")

        grid_card=ctk.CTkFrame(left,corner_radius=20,fg_color="#061522",border_width=1,border_color=PREMIUM_UI["card_border_soft"])
        grid_card.grid(row=1,column=0,sticky="nsew"); grid_card.grid_rowconfigure(1,weight=1); grid_card.grid_columnconfigure(0,weight=1)
        sheetbar=ctk.CTkFrame(grid_card,height=38,corner_radius=12,fg_color="#0A2037")
        sheetbar.grid(row=0,column=0,sticky="ew",padx=8,pady=(8,0)); sheetbar.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(sheetbar,text="ACA / MASTER GRADE SHEET",text_color=PREMIUM_UI["cyan"],font=self._font(7,"bold",FONT_MONO)).grid(row=0,column=0,sticky="w",padx=9,pady=7)
        ctk.CTkLabel(sheetbar,text="⇧ wheel  •  Ctrl/Cmd + wheel  •  arrows  •  Enter",text_color=PREMIUM_UI["muted"],font=self._font(7)).grid(row=0,column=1,sticky="e",padx=7)
        self.journal_left_button=ctk.CTkButton(sheetbar,text="‹",width=30,height=26,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(12,"bold"),command=lambda:self.grade_grid.scroll_x(-1)); self.journal_left_button.grid(row=0,column=2,padx=2); attach_tooltip(self.journal_left_button,"journal_scroll_left")
        self.journal_right_button=ctk.CTkButton(sheetbar,text="›",width=30,height=26,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(12,"bold"),command=lambda:self.grade_grid.scroll_x(1)); self.journal_right_button.grid(row=0,column=3,padx=(2,7)); attach_tooltip(self.journal_right_button,"journal_scroll_right")
        self.grade_grid=PremiumGradeGrid(grid_card,self); self.grade_grid.grid(row=1,column=0,sticky="nsew",padx=8,pady=(5,8))

        bottom=ctk.CTkFrame(left,fg_color="transparent",height=182); bottom.grid(row=2,column=0,sticky="ew",pady=(8,0)); bottom.grid_columnconfigure(0,weight=3); bottom.grid_columnconfigure(1,weight=2)
        activity=ctk.CTkFrame(bottom,corner_radius=20,fg_color="#061522",border_width=1,border_color=PREMIUM_UI["card_border_soft"]); activity.grid(row=0,column=0,sticky="nsew",padx=(0,5))
        ah=ctk.CTkFrame(activity,fg_color="transparent"); ah.pack(fill="x",padx=12,pady=(9,3))
        ctk.CTkLabel(ah,text="",image=self._icon("clock",18,PREMIUM_UI["cyan"]),width=22).pack(side="left")
        ctk.CTkLabel(ah,text=tr("Recent activity"),text_color=PREMIUM_UI["text"],font=self._font(10,"bold")).pack(side="left",padx=(5,0))
        self.journal_activity_box=ctk.CTkFrame(activity,fg_color="transparent"); self.journal_activity_box.pack(fill="both",expand=True,padx=7,pady=(0,7))

        quick=ctk.CTkFrame(bottom,corner_radius=20,fg_color="#061522",border_width=1,border_color=PREMIUM_UI["card_border_soft"]); quick.grid(row=0,column=1,sticky="nsew",padx=(5,0))
        qh=ctk.CTkFrame(quick,fg_color="transparent"); qh.pack(fill="x",padx=12,pady=(9,5))
        ctk.CTkLabel(qh,text="",image=self._icon("bolt",18,PREMIUM_UI["cyan"]),width=22).pack(side="left")
        ctk.CTkLabel(qh,text=tr("Quick actions"),text_color=PREMIUM_UI["text"],font=self._font(10,"bold")).pack(side="left",padx=(5,0))
        actions=[
            ("Add grade","plus","#0D78FF","#1592FF",self._quick_add_grade),
            ("Create student","access","#633DF0","#7655FF",self.open_add_student),
            ("Export report","export","#0BCB91","#19E6AE",self.export_graduation_report),
            ("Backup database","backup","#183B65","#23568C",self.backup_database),
        ]
        for text,kind,color,hover,cmd in actions:
            state="normal" if (text not in ("Create student","Backup database") or self.is_admin()) else "disabled"
            b=ctk.CTkButton(quick,text=tr(text),image=self._icon(kind,16,"white",glow=False),compound="left",height=32,corner_radius=11,fg_color=color,hover_color=hover,border_width=0,text_color="white",font=self._font(8,"bold"),command=cmd,state=state)
            b.pack(fill="x",padx=10,pady=2)

        rail=ctk.CTkScrollableFrame(content,width=316,corner_radius=20,fg_color="#05111F",border_width=1,border_color=PREMIUM_UI["card_border_soft"],scrollbar_button_color="#143D63",scrollbar_button_hover_color="#1B5A88")
        rail.grid(row=0,column=1,sticky="nsew",padx=(7,0))

        profile=ctk.CTkFrame(rail,corner_radius=20,fg_color="#071725",border_width=1,border_color="#12517F"); profile.pack(fill="x",padx=4,pady=(4,8))
        head=ctk.CTkFrame(profile,fg_color="transparent"); head.pack(fill="x",padx=12,pady=(12,6))
        self.journal_profile_avatar=ctk.CTkLabel(head,text="—",width=56,height=56,corner_radius=28,fg_color="#7456F3",text_color="white",font=self._font(20,"bold")); self.journal_profile_avatar.pack(side="left")
        info=ctk.CTkFrame(head,fg_color="transparent"); info.pack(side="left",fill="x",expand=True,padx=(10,0))
        self.journal_profile_name=ctk.CTkLabel(info,text=tr("No student"),text_color=PREMIUM_UI["text"],font=self._font(15,"bold"),anchor="w"); self.journal_profile_name.pack(anchor="w")
        self.journal_profile_meta=ctk.CTkLabel(info,text="",text_color=PREMIUM_UI["muted"],font=self._font(8),anchor="w"); self.journal_profile_meta.pack(anchor="w",pady=(2,0))
        ctk.CTkLabel(head,text=f"● {tr('Active')}",text_color=PREMIUM_UI["green"],fg_color="#073126",corner_radius=12,height=25,padx=7,font=self._font(7,"bold")).pack(side="right",anchor="n")
        self.journal_profile_skill=ctk.CTkLabel(profile,text="—",height=32,corner_radius=12,fg_color="#0A233B",text_color="#9BC7F0",font=self._font(8,"bold")); self.journal_profile_skill.pack(fill="x",padx=12,pady=(2,8))
        self.journal_track_frame=ctk.CTkFrame(profile,fg_color="transparent"); self.journal_track_frame.pack(fill="x",padx=12,pady=(0,10))
        metrics=ctk.CTkFrame(profile,corner_radius=14,fg_color="#061522",border_width=1,border_color="#0C3455"); metrics.pack(fill="x",padx=12,pady=(0,12))
        for _col in range(3): metrics.grid_columnconfigure(_col,weight=1)
        self.journal_profile_metrics={}
        for i,(key,label) in enumerate((("gpa","GPA"),("grades",tr("Grades")),("avg",tr("AVG")))):
            ctk.CTkLabel(metrics,text=label,text_color=PREMIUM_UI["muted"],font=self._font(7)).grid(row=0,column=i,pady=(8,0))
            v=ctk.CTkLabel(metrics,text="—",text_color=PREMIUM_UI["text"],font=self._font(16,"bold")); v.grid(row=1,column=i,pady=(0,8)); self.journal_profile_metrics[key]=v

        progress=ctk.CTkFrame(rail,corner_radius=20,fg_color="#071725",border_width=1,border_color="#12517F"); progress.pack(fill="x",padx=4,pady=(0,8))
        ph=ctk.CTkFrame(progress,fg_color="transparent"); ph.pack(fill="x",padx=12,pady=(10,6)); ctk.CTkLabel(ph,text="",image=self._icon("analytics",17,PREMIUM_UI["cyan"]),width=21).pack(side="left"); ctk.CTkLabel(ph,text=tr("Progress by phase"),text_color=PREMIUM_UI["text"],font=self._font(10,"bold")).pack(side="left",padx=(4,0))
        self.journal_phase_progress={}
        for p in range(1,8):
            row=ctk.CTkFrame(progress,fg_color="transparent"); row.pack(fill="x",padx=12,pady=3)
            top=ctk.CTkFrame(row,fg_color="transparent"); top.pack(fill="x")
            ctk.CTkLabel(top,text=f"{tr('Phase')} {p}",text_color=PREMIUM_UI["text2"],font=self._font(8),anchor="w").pack(side="left")
            pct=ctk.CTkLabel(top,text="0%",text_color=PREMIUM_UI["text2"],font=self._font(8),anchor="e"); pct.pack(side="right")
            bar=ctk.CTkProgressBar(row,height=8,corner_radius=8,fg_color="#162A43",progress_color=PREMIUM_UI["cyan"]); bar.pack(fill="x",pady=(2,0)); bar.set(0)
            self.journal_phase_progress[p]=(bar,pct)
        ctk.CTkFrame(progress,height=6,fg_color="transparent").pack()

        inspector=ctk.CTkFrame(rail,corner_radius=20,fg_color="#071725",border_width=1,border_color="#104A75"); inspector.pack(fill="x",padx=4,pady=(0,4))
        ih=ctk.CTkFrame(inspector,fg_color="transparent"); ih.pack(fill="x",padx=12,pady=(10,2)); ctk.CTkLabel(ih,text="",image=self._icon("book",17,PREMIUM_UI["cyan"]),width=21).pack(side="left"); ctk.CTkLabel(ih,text=tr("Lesson details"),text_color=PREMIUM_UI["text"],font=self._font(10,"bold")).pack(side="left",padx=(4,0))
        self.inspector_title=ctk.CTkLabel(inspector,text=tr("Select a lesson"),text_color=PREMIUM_UI["text2"],font=self._font(10,"bold"),wraplength=260,justify="left"); self.inspector_title.pack(anchor="w",padx=12,pady=(6,2))
        self.inspector_meta=ctk.CTkLabel(inspector,text="",text_color=PREMIUM_UI["muted"],font=self._font(8),wraplength=260,justify="left"); self.inspector_meta.pack(anchor="w",padx=12,pady=(0,8))
        ctk.CTkLabel(inspector,text="GEOMETRY DASH LEVEL ID",text_color=PREMIUM_UI["muted"],font=self._font(7,"bold",FONT_MONO)).pack(anchor="w",padx=12,pady=(6,3))
        self.level_id_entry=ctk.CTkEntry(inspector,height=34,corner_radius=11,fg_color="#061522",border_width=1,border_color="#16486F",placeholder_text="12345678"); self.level_id_entry.pack(fill="x",padx=12); attach_tooltip(self.level_id_entry,"level_id")
        ctk.CTkButton(inspector,text=tr("Save Level ID"),height=31,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(8,"bold"),command=self.save_level_id).pack(fill="x",padx=12,pady=(5,10))
        ctk.CTkLabel(inspector,text="SHOWCASE URL",text_color=PREMIUM_UI["muted"],font=self._font(7,"bold",FONT_MONO)).pack(anchor="w",padx=12,pady=(2,3))
        self.showcase_entry=ctk.CTkEntry(inspector,height=34,corner_radius=11,fg_color="#061522",border_width=1,border_color="#16486F",placeholder_text="YouTube / Shorts / TikTok"); self.showcase_entry.pack(fill="x",padx=12); attach_tooltip(self.showcase_entry,"showcase_url")
        ctk.CTkButton(inspector,text=tr("Save showcase"),height=31,corner_radius=10,fg_color="#0D2844",hover_color="#143A5F",font=self._font(8,"bold"),command=self.save_showcase_url).pack(fill="x",padx=12,pady=(5,10))
        self.inspector_grade_info=ctk.CTkTextbox(inspector,height=130,corner_radius=14,fg_color="#05111F",border_width=1,border_color="#0C3455",font=self._font(8)); self.inspector_grade_info.pack(fill="x",padx=12,pady=(0,12)); self.inspector_grade_info.configure(state="disabled")

    def _build_analytics(self):
        page=self.pages["analytics"]; page.grid_columnconfigure(0,weight=1); page.grid_rowconfigure(2,weight=1)
        controls=ctk.CTkFrame(page,corner_radius=21,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"])
        controls.grid(row=0,column=0,sticky="ew",pady=(0,12)); controls.grid_columnconfigure(5,weight=1)
        ctk.CTkLabel(controls,text="Clutch GPA simulator",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).grid(row=0,column=0,columnspan=4,sticky="w",padx=16,pady=(12,2))
        ctk.CTkLabel(controls,text="Calculate exact flawless-score vector across remaining lessons",text_color=PREMIUM_UI["muted"],font=self._font(9)).grid(row=1,column=0,columnspan=4,sticky="w",padx=16,pady=(0,12))
        self.target_var=tk.StringVar(value=str(self.model.settings.get("probation_threshold",8.9)))
        ctk.CTkLabel(controls,text="Target GPA",text_color=PREMIUM_UI["muted"],font=self._font(9,"bold")).grid(row=0,column=5,sticky="e",padx=(10,6))
        target=ctk.CTkEntry(controls,textvariable=self.target_var,width=86,height=36,corner_radius=12,fg_color=PREMIUM_UI["surface2"],border_width=1,border_color="#16486F")
        target.grid(row=0,column=6,rowspan=2,sticky="e",padx=(0,8))
        ctk.CTkButton(controls,text="Run simulation",width=132,height=40,corner_radius=12,fg_color=PREMIUM_UI["cyan2"],hover_color="#30BFFF",text_color="#071018",font=self._font(9,"bold"),command=self.run_clutch).grid(row=0,column=7,rowspan=2,padx=(0,14))
        metrics=ctk.CTkFrame(page,fg_color="transparent"); metrics.grid(row=1,column=0,sticky="ew",pady=(0,12))
        for i in range(4): metrics.grid_columnconfigure(i,weight=1)
        self.analytics_values={}
        for i,(key,title,accent) in enumerate([("current","Current GPA",PREMIUM_UI["cyan"]),("consistency","Consistency",PREMIUM_UI["green"]),("needed","10/10 needed",PREMIUM_UI["violet"]),("impact","HW impact",PREMIUM_UI["amber"])]):
            card,val=self._metric_card(metrics,title,accent); card.grid(row=0,column=i,sticky="ew",padx=(0 if i==0 else 5,0 if i==3 else 5)); self.analytics_values[key]=val
        lower=ctk.CTkFrame(page,fg_color="transparent"); lower.grid(row=2,column=0,sticky="nsew"); lower.grid_columnconfigure(0,weight=3); lower.grid_columnconfigure(1,weight=2); lower.grid_rowconfigure(0,weight=1)
        chart_card=ctk.CTkFrame(lower,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"]); chart_card.grid(row=0,column=0,sticky="nsew",padx=(0,7))
        ctk.CTkLabel(chart_card,text="Projection",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w",padx=16,pady=(14,0))
        self.projection_chart=ProjectionChart(chart_card,self); self.projection_chart.pack(fill="both",expand=True,padx=12,pady=(6,12))
        report=ctk.CTkFrame(lower,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"]); report.grid(row=0,column=1,sticky="nsew",padx=(7,0))
        ctk.CTkLabel(report,text="Strategic output",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w",padx=16,pady=(14,6))
        self.analytics_text=ctk.CTkTextbox(report,corner_radius=15,fg_color="#061522",border_width=1,border_color="#0C3455",font=self._font(10))
        self.analytics_text.pack(fill="both",expand=True,padx=16,pady=(0,16)); self.analytics_text.configure(state="disabled")

    def _build_graduation(self):
        page=self.pages["graduation"]; page.grid_columnconfigure(0,weight=1); page.grid_columnconfigure(1,weight=1); page.grid_rowconfigure(1,weight=1)
        hero=ctk.CTkFrame(page,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"])
        hero.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,12)); hero.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(hero,text="Grand 100-point Solo-Level Exam",text_color=PREMIUM_UI["text"],font=self._font(18,"bold")).grid(row=0,column=0,sticky="w",padx=18,pady=(15,2))
        ctk.CTkLabel(hero,text="1:20+ long-form graduation layout",text_color=PREMIUM_UI["muted"],font=self._font(10)).grid(row=1,column=0,sticky="w",padx=18,pady=(0,15))
        self.exam_score_var=tk.DoubleVar(value=0)
        self.exam_score_label=ctk.CTkLabel(hero,text="0 / 100",text_color=PREMIUM_UI["green"],font=self._font(22,"bold",FONT_MONO)); self.exam_score_label.grid(row=0,column=2,rowspan=2,padx=18)
        left=ctk.CTkFrame(page,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"]); left.grid(row=1,column=0,sticky="nsew",padx=(0,7))
        ctk.CTkLabel(left,text="Exam score",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w",padx=18,pady=(16,4))
        self.exam_slider=ctk.CTkSlider(left,from_=0,to=100,number_of_steps=100,height=20,progress_color=PREMIUM_UI["green"],button_color=PREMIUM_UI["text"],button_hover_color=PREMIUM_UI["cyan"],command=self.on_exam_score)
        self.exam_slider.pack(fill="x",padx=18,pady=(10,10)); self.exam_slider.set(0)
        ctk.CTkButton(left,text="Save exam score",height=40,corner_radius=12,fg_color=PREMIUM_UI["cyan2"],hover_color="#30BFFF",text_color="#071018",font=self._font(10,"bold"),command=self.save_exam_score).pack(fill="x",padx=18,pady=(0,18))
        ctk.CTkLabel(left,text="Moderator send requests",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w",padx=18,pady=(6,8))
        self.mod_vars={}
        for key,label in [("gameplay","Gameplay moderator request"),("art","Art review request"),("verification","Verification request")]:
            var=tk.BooleanVar(value=bool(self.model.settings.get("moderator_requests",{}).get(key,False))); self.mod_vars[key]=var
            cb=ctk.CTkCheckBox(left,text=label,variable=var,checkbox_width=20,checkbox_height=20,corner_radius=6,border_color=PREMIUM_UI["line"],fg_color=PREMIUM_UI["cyan2"],hover_color=PREMIUM_UI["cyan"],font=self._font(10),command=self.save_moderator_requests)
            cb.pack(anchor="w",padx=18,pady=6)
        right=ctk.CTkFrame(page,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"]); right.grid(row=1,column=1,sticky="nsew",padx=(7,0))
        ctk.CTkLabel(right,text="Graduation dossier",text_color=PREMIUM_UI["text"],font=self._font(14,"bold")).pack(anchor="w",padx=18,pady=(16,4))
        ctk.CTkLabel(right,text="Generate a polished HTML performance report with GPA, phase analytics and grade ledger.",text_color=PREMIUM_UI["muted"],font=self._font(10),wraplength=430,justify="left").pack(anchor="w",padx=18,pady=(0,18))
        self.grad_summary=ctk.CTkTextbox(right,height=260,corner_radius=15,fg_color="#061522",border_width=1,border_color="#0C3455",font=self._font(10)); self.grad_summary.pack(fill="both",expand=True,padx=18,pady=(0,16)); self.grad_summary.configure(state="disabled")
        ctk.CTkButton(right,text="Export graduation report",height=42,corner_radius=13,fg_color=PREMIUM_UI["green2"],hover_color=PREMIUM_UI["green"],text_color="#07150F",font=self._font(10,"bold"),command=self.export_graduation_report).pack(fill="x",padx=18,pady=(0,18))

    def _build_access(self):
        page=self.pages["access"]; page.grid_columnconfigure(0,weight=2); page.grid_columnconfigure(1,weight=3); page.grid_rowconfigure(0,weight=1)
        create=ctk.CTkFrame(page,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"]); create.grid(row=0,column=0,sticky="nsew",padx=(0,7))
        ctk.CTkLabel(create,text="Teacher onboarding",text_color=PREMIUM_UI["text"],font=self._font(16,"bold")).pack(anchor="w",padx=18,pady=(16,2))
        ctk.CTkLabel(create,text="Generate one-time invite codes with explicit phase-level edit permissions.",text_color=PREMIUM_UI["muted"],font=self._font(10),wraplength=360,justify="left").pack(anchor="w",padx=18,pady=(0,16))
        ctk.CTkLabel(create,text="TEACHER LABEL",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=18,pady=(4,4))
        self.teacher_label_entry=ctk.CTkEntry(create,height=40,corner_radius=12,fg_color=PREMIUM_UI["surface2"],border_width=1,border_color="#16486F",placeholder_text="Deco Instructor")
        self.teacher_label_entry.pack(fill="x",padx=18)
        ctk.CTkLabel(create,text="AUTHORIZED PHASES",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=18,pady=(16,6))
        self.phase_access_vars={}
        phasebox=ctk.CTkFrame(create,fg_color="transparent"); phasebox.pack(fill="x",padx=18)
        for i in range(1,8):
            var=tk.BooleanVar(value=(i==7)); self.phase_access_vars[i]=var
            cb=ctk.CTkCheckBox(phasebox,text=f"Phase {i}",variable=var,width=100,checkbox_width=19,checkbox_height=19,corner_radius=5,border_color=PREMIUM_UI["line"],fg_color=_phase_accent(i),hover_color=_phase_accent(i),font=self._font(9))
            cb.grid(row=(i-1)//2,column=(i-1)%2,sticky="w",padx=(0,12),pady=5)
        ctk.CTkButton(create,text="Generate invite code",height=42,corner_radius=13,fg_color=PREMIUM_UI["cyan2"],hover_color="#30BFFF",text_color="#071018",font=self._font(10,"bold"),command=self.generate_teacher_invite).pack(fill="x",padx=18,pady=(20,8))
        self.generated_code=ctk.CTkLabel(create,text="",text_color=PREMIUM_UI["green"],font=self._font(15,"bold",FONT_MONO)); self.generated_code.pack(anchor="w",padx=18,pady=(6,16))
        listcard=ctk.CTkFrame(page,corner_radius=22,fg_color=PREMIUM_UI["surface"],border_width=1,border_color=PREMIUM_UI["card_border_soft"]); listcard.grid(row=0,column=1,sticky="nsew",padx=(7,0)); listcard.grid_rowconfigure(1,weight=1); listcard.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(listcard,text="Invites & account registry",text_color=PREMIUM_UI["text"],font=self._font(16,"bold")).grid(row=0,column=0,sticky="w",padx=18,pady=(16,8))
        self.invite_scroll=ctk.CTkScrollableFrame(listcard,corner_radius=16,fg_color="#061522",scrollbar_button_color=PREMIUM_UI["surface3"],scrollbar_button_hover_color=PREMIUM_UI["hover"])
        self.invite_scroll.grid(row=1,column=0,sticky="nsew",padx=14,pady=(0,14))

    def active_sid(self):
        if self.is_student():
            return self.auth_context.get("student_id")
        return self._active_student_id if self._active_student_id in self.model.students else None

    def role(self):
        return self.auth_context

    def is_admin(self):
        return self.auth_context.get("role") == "ADMIN"

    def is_teacher(self):
        return self.auth_context.get("role") == "TEACHER"

    def is_student(self):
        return self.auth_context.get("role") == "STUDENT"

    def role_label(self):
        return tr({"ADMIN":"Principal Admin","TEACHER":"Teacher","STUDENT":"Student"}.get(self.auth_context.get("role"), "User"))

    def can_manage_graduation(self):
        return bool(self.auth_context.get("permissions", {}).get("manage_graduation"))

    def open_security(self):
        user_id = self.auth_context.get("user_id")
        if not user_id:
            return
        win = ctk.CTkToplevel(self)
        win.title(tr("Account security"))
        win.geometry("540x610")
        win.resizable(False, False)
        win.configure(fg_color=PREMIUM_UI["bg"])
        win.transient(self)
        win.grab_set()
        card = ctk.CTkFrame(win, corner_radius=22, fg_color=PREMIUM_UI["surface"], border_width=1, border_color=PREMIUM_UI["card_border_soft"])
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(card, text="Account security", text_color=PREMIUM_UI["text"], font=self._font(20, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        ctk.CTkLabel(card, text=f"@{self.auth_context.get('username','')}  •  {self.role_label()}", text_color=PREMIUM_UI["muted"], font=self._font(9)).pack(anchor="w", padx=18, pady=(0, 14))

        def field(label, placeholder="", show=None):
            ctk.CTkLabel(card, text=label, text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=18, pady=(9, 4))
            e = ctk.CTkEntry(card, height=40, corner_radius=12, fg_color=PREMIUM_UI["surface2"], border_width=1, border_color="#16486F", placeholder_text=placeholder, show=show)
            e.pack(fill="x", padx=18)
            return e

        current = field("CURRENT PASSWORD", "Required for security changes", "•")
        new_password = field("NEW PASSWORD", "At least 8 characters", "•")
        confirm = field("CONFIRM NEW PASSWORD", "Repeat new password", "•")
        status = ctk.CTkLabel(card, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=460, justify="left")
        status.pack(anchor="w", padx=18, pady=(10, 0))

        def show_new_code(code, title):
            try:
                self.clipboard_clear(); self.clipboard_append(code)
            except Exception:
                pass
            messagebox.showinfo(title, f"Save this new recovery code:\n\n{code}\n\nIt has been copied to the clipboard. The previous recovery code is now invalid.", parent=win)

        def save_password():
            try:
                if new_password.get() != confirm.get():
                    raise ValueError("Passwords do not match.")
                result = self.auth_manager.change_password(user_id, current.get(), new_password.get())
                show_new_code(result.get("recovery_code_once"), "Password changed")
                current.delete(0, "end"); new_password.delete(0, "end"); confirm.delete(0, "end")
                status.configure(text=tr("Password updated securely."), text_color=PREMIUM_UI["green"])
                self.set_status("Password changed")
            except Exception as exc:
                status.configure(text=tr_error(exc), text_color=PREMIUM_UI["pink"])

        def regenerate_code():
            try:
                code = self.auth_manager.regenerate_recovery_code(user_id, current.get())
                show_new_code(code, "Recovery code replaced")
                current.delete(0, "end")
                status.configure(text=tr("Recovery code replaced. Old code invalidated."), text_color=PREMIUM_UI["green"])
                self.set_status("Recovery code regenerated")
            except Exception as exc:
                status.configure(text=tr_error(exc), text_color=PREMIUM_UI["pink"])

        ctk.CTkButton(card, text="Change password", height=40, corner_radius=10, fg_color=PREMIUM_UI["cyan2"], hover_color="#30BFFF", text_color="#071018", font=self._font(10, "bold"), command=save_password).pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkFrame(card, height=1, fg_color=PREMIUM_UI["line_soft"]).pack(fill="x", padx=18, pady=10)
        ctk.CTkLabel(card, text="RECOVERY CODE", text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=18)
        ctk.CTkLabel(card, text="If you lose the current recovery code, enter your current password above and issue a replacement. The old code becomes invalid immediately.", text_color=PREMIUM_UI["text2"], font=self._font(9), wraplength=460, justify="left").pack(anchor="w", padx=18, pady=(5, 9))
        replace_recovery_button = ctk.CTkButton(card, text="Replace recovery code", height=38, corner_radius=10, fg_color=PREMIUM_UI["surface3"], hover_color=PREMIUM_UI["hover"], text_color=PREMIUM_UI["text2"], font=self._font(9, "bold"), command=regenerate_code)
        replace_recovery_button.pack(fill="x", padx=18, pady=(0, 18))
        attach_tooltip(replace_recovery_button, "recovery_replace")
        localize_widget_tree(win)
        attach_tooltip(current, "security")
        current.focus_set()

    def logout(self):
        try:
            logout_fn = getattr(self.auth_manager, "logout", None)
            if callable(logout_fn):
                logout_fn()
        except Exception:
            pass
        self.logout_requested = True
        self.destroy()

    def set_status(self,text):
        message = text or "Ready"
        self.status_var.set(tr(message))
        if not hasattr(self, "status"):
            return
        if getattr(self, "_status_restore_job", None):
            try: self.after_cancel(self._status_restore_job)
            except Exception: pass
        if text:
            self.status.configure(text_color=PREMIUM_UI["cyan"])
            self._status_restore_job = self.after(900, lambda: self.status.configure(text_color=PREMIUM_UI["muted"]))
        else:
            self.status.configure(text_color=PREMIUM_UI["muted"])

    def on_student_combo(self,label):
        sid=self.student_label_to_id.get(label)
        if sid and sid in self.model.students and sid != self._active_student_id:
            self._active_student_id = sid
            self.refresh_all()

    def on_phase_filter(self, value):
        self.grade_grid.set_phase(0 if value == tr("All") else int(value[1:]))

    def on_journal_status(self, value):
        reverse = {tr("All"): "All", tr("Graded"): "Graded", tr("Active"): "Active", tr("Empty"): "Empty", tr("At risk"): "At risk"}
        self.grade_grid.set_status_filter(reverse.get(value, value))

    def on_journal_search(self, _event=None):
        if getattr(self, "_journal_search_job", None):
            try:
                self.after_cancel(self._journal_search_job)
            except Exception:
                pass
        value = self.journal_search_var.get()
        self._journal_search_job = self.after(100, lambda: self.grade_grid.set_search_filter(value))

    def on_journal_zoom(self, value):
        pct = int(round(float(value)))
        self.grade_grid.set_zoom(pct)

    def on_journal_density(self, value):
        reverse = {tr("Compact"): "Compact", tr("Comfort"): "Comfort", tr("Spacious"): "Spacious"}
        self.grade_grid.set_density(reverse.get(value, value))

    def on_journal_jump(self):
        self.grade_grid.jump_to(self.journal_jump_var.get())

    def on_journal_active(self):
        self.grade_grid.jump_active()

    def set_inspector_lesson(self,lesson_id):
        self.inspector_lesson_id=lesson_id
        lesson=LESSON_BY_ID[lesson_id]
        self.inspector_title.configure(text=f"{lesson_id}  {localize_lesson_name(lesson['name'])}")
        self.inspector_meta.configure(text=tr(f"Phase {lesson['phase']} • {lesson['phase_name']}\nBase phase weight {lesson['weight']:.1f}× • default assessment ×{lesson.get('default_assessment_weight',1)}"))
        sid=self.active_sid(); rec=self.model.get_record(sid,lesson_id) if sid else None
        self.level_id_entry.delete(0,"end"); self.level_id_entry.insert(0,(rec or {}).get("level_id_link") or "")
        self.showcase_entry.delete(0,"end"); self.showcase_entry.insert(0,(rec or {}).get("showcase_pipeline_url") or "")
        grades=self.model.get_grades(sid,lesson_id) if sid else []
        lines=[]
        for i,e in enumerate(grades,1):
            grade_time = format_datetime_localized(e.get("timestamp"))
            lines.append(f"#{i:02d}  {_fmt_grade(e.get('grade',0))}/10   ×{e.get('weight_multiplier',1)}   {localize_assessment_type(e.get('assessment_type',''))}\n     {grade_time}{'  • ' + tr('HW skip') if e.get('homework_skipped') else ''}")
        self.inspector_grade_info.configure(state="normal"); self.inspector_grade_info.delete("1.0","end"); self.inspector_grade_info.insert("1.0","\n\n".join(lines) if lines else tr("No grades yet. Double-click the first empty grade cell to add one.")); self.inspector_grade_info.configure(state="disabled")

    def can_edit_submission_links(self, lesson_id):
        if lesson_id not in LESSON_BY_ID:
            return False
        if self.is_admin():
            return True
        if self.is_teacher():
            return LESSON_BY_ID[lesson_id]["phase"] in {int(p) for p in self.auth_context.get("authorized_phases", [])}
        if self.is_student():
            return self.active_sid() == self.auth_context.get("student_id")
        return False

    def save_level_id(self):
        if not self.inspector_lesson_id or not self.active_sid(): return
        if not self.can_edit_submission_links(self.inspector_lesson_id):
            messagebox.showerror("Access denied", "You cannot edit submissions for this lesson.", parent=self); return
        try:
            self.model.set_level_id_link(self.active_sid(),self.inspector_lesson_id,self.level_id_entry.get())
            self.set_status("Level ID saved")
        except Exception as exc: messagebox.showerror("Level ID",tr_error(exc),parent=self)

    def save_showcase_url(self):
        if not self.inspector_lesson_id or not self.active_sid(): return
        if not self.can_edit_submission_links(self.inspector_lesson_id):
            messagebox.showerror("Access denied", "You cannot edit submissions for this lesson.", parent=self); return
        try:
            self.model.set_showcase_pipeline_url(self.active_sid(),self.inspector_lesson_id,self.showcase_entry.get())
            self.set_status("Showcase URL saved")
        except Exception as exc: messagebox.showerror("Showcase URL",tr_error(exc),parent=self)

    def open_grade_modal(self,lesson_id,grade_index=None):
        sid=self.active_sid()
        if not sid: return
        lesson=LESSON_BY_ID[lesson_id]
        if not self.model.can_edit_phase(self.role(),lesson["phase"]):
            messagebox.showerror("Access denied",f"{self.role_label()} cannot grade Phase {lesson['phase']}.",parent=self); return
        existing=self.model.get_grades(sid,lesson_id)
        entry=existing[grade_index] if grade_index is not None and 0<=grade_index<len(existing) else None
        win=ctk.CTkToplevel(self); win.title(tr("Grade transaction")); win.geometry("520x590"); win.resizable(False,False); win.configure(fg_color=PREMIUM_UI["bg"]); win.transient(self); win.grab_set()
        ctk.CTkLabel(win,text=f"{lesson_id}  {localize_lesson_name(lesson['name'])}",text_color=PREMIUM_UI["text"],font=self._font(18,"bold"),wraplength=470,justify="left").pack(anchor="w",padx=24,pady=(24,4))
        ctk.CTkLabel(win,text=tr(f"Phase {lesson['phase']} • base phase weight {lesson['weight']:.1f}×"),text_color=PREMIUM_UI["muted"],font=self._font(10)).pack(anchor="w",padx=24,pady=(0,18))
        ctk.CTkLabel(win,text="SCORE / 10",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=24,pady=(2,4))
        score=ctk.CTkEntry(win,height=44,corner_radius=11,fg_color=PREMIUM_UI["surface2"],border_color=PREMIUM_UI["line"],font=self._font(18,"bold",FONT_MONO)); score.pack(fill="x",padx=24); score.insert(0,_fmt_grade(entry.get("grade")) if entry else "")
        ctk.CTkLabel(win,text="ASSESSMENT WEIGHT",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=24,pady=(18,6))
        weight_var=tk.StringVar(value=f"×{int(entry.get('weight_multiplier',lesson.get('default_assessment_weight',1)) if entry else lesson.get('default_assessment_weight',1))}")
        weights=ctk.CTkSegmentedButton(win,values=["×1","×2","×3","×4"],variable=weight_var,height=38,corner_radius=10,selected_color=PREMIUM_UI["cyan2"],selected_hover_color="#30BFFF",unselected_color=PREMIUM_UI["surface2"],unselected_hover_color=PREMIUM_UI["hover"]); weights.pack(fill="x",padx=24)
        ctk.CTkLabel(win,text="ASSESSMENT TYPE",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=24,pady=(18,6))
        type_values=[tr(GradeWeightPolicy.LABELS[i]) for i in VALID_ASSESSMENT_WEIGHTS]
        type_var=tk.StringVar(value=localize_assessment_type(entry.get("assessment_type") if entry else GradeWeightPolicy.LABELS[int(weight_var.get()[1:])]))
        typ=ctk.CTkComboBox(win,values=type_values,variable=type_var,height=40,corner_radius=12,fg_color=PREMIUM_UI["surface2"],border_width=1,border_color="#16486F",button_color=PREMIUM_UI["surface3"],button_hover_color=PREMIUM_UI["hover"],dropdown_fg_color=PREMIUM_UI["surface2"],dropdown_hover_color=PREMIUM_UI["hover"]); typ.pack(fill="x",padx=24)
        hw_var=tk.BooleanVar(value=bool(entry.get("homework_skipped")) if entry else False)
        ctk.CTkSwitch(win,text="Homework skipped / delinquent",variable=hw_var,progress_color=PREMIUM_UI["amber"],button_color=PREMIUM_UI["text"],font=self._font(10)).pack(anchor="w",padx=24,pady=(18,10))
        def save():
            try:
                g=float(score.get().replace(",",".")); mult=int(weight_var.get()[1:])
                if entry is None:
                    self.model.submit_grade(sid,lesson_id,g,hw_var.get(),self.role(),mult,canonical_assessment_type(type_var.get()))
                else:
                    self.model.update_grade(sid,lesson_id,grade_index,g,hw_var.get(),self.role(),mult,canonical_assessment_type(type_var.get()))
                win.destroy(); self.refresh_all(); self.set_inspector_lesson(lesson_id)
            except Exception as exc: messagebox.showerror("Grade",tr_error(exc),parent=win)
        buttons=ctk.CTkFrame(win,fg_color="transparent"); buttons.pack(side="bottom",fill="x",padx=24,pady=24)
        ctk.CTkButton(buttons,text="Save transaction",height=42,corner_radius=13,fg_color=PREMIUM_UI["cyan2"],hover_color="#30BFFF",text_color="#071018",font=self._font(10,"bold"),command=save).pack(side="left",fill="x",expand=True)
        if entry is not None:
            def delete():
                if messagebox.askyesno("Delete grade","Delete this grade transaction?",parent=win):
                    self.model.delete_grade(sid,lesson_id,grade_index,self.role()); win.destroy(); self.refresh_all(); self.set_inspector_lesson(lesson_id)
            ctk.CTkButton(buttons,text="Delete",width=92,height=40,corner_radius=11,fg_color="#45202A",hover_color="#5A2835",text_color=PREMIUM_UI["pink"],font=self._font(10,"bold"),command=delete).pack(side="right",padx=(10,0))
        localize_widget_tree(win)
        score.focus_set()

    def open_add_student(self):
        if not self.is_admin():
            messagebox.showerror("Access denied", "Only the Principal Administrator can create additional student profiles.", parent=self); return
        win=ctk.CTkToplevel(self); win.title(tr("New student")); win.geometry("480x510"); win.resizable(False,False); win.transient(self); win.grab_set(); win.configure(fg_color=PREMIUM_UI["bg"])
        ctk.CTkLabel(win,text="Create student profile",text_color=PREMIUM_UI["text"],font=self._font(20,"bold")).pack(anchor="w",padx=24,pady=(24,4))
        ctk.CTkLabel(win,text="A new profile starts with an empty 120-lesson ledger.",text_color=PREMIUM_UI["muted"],font=self._font(10)).pack(anchor="w",padx=24,pady=(0,18))
        fields={}
        for key,label,placeholder in [("name",tr("NAME"),tr("Student name")),("age",tr("AGE"),"13"),("skill",tr("SKILL CLASS"),tr("Unranked")),("tracks",tr("ACTIVE TRACKS"),f"{track_display_value('Gameplay')}, {track_display_value('Decoration')}")]:
            ctk.CTkLabel(win,text=label,text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=24,pady=(10,4))
            ent=ctk.CTkEntry(win,height=40,corner_radius=12,fg_color=PREMIUM_UI["surface2"],border_width=1,border_color="#16486F",placeholder_text=placeholder); ent.pack(fill="x",padx=24); fields[key]=ent
        fields["tracks"].insert(0,f"{track_display_value('Gameplay')}, {track_display_value('Decoration')}")
        def create():
            try:
                sid=self.model.add_student(fields["name"].get().strip(),int(fields["age"].get()),fields["skill"].get().strip() or "Unranked",[canonical_track_value(x) for x in fields["tracks"].get().split(",") if x.strip()]); win.destroy(); self.model.set_active_student(sid); self.refresh_all()
            except Exception as exc: messagebox.showerror("New student",tr_error(exc),parent=win)
        ctk.CTkButton(win,text="Create profile",height=42,corner_radius=11,fg_color=PREMIUM_UI["green2"],hover_color=PREMIUM_UI["green"],text_color="#07150F",font=self._font(10,"bold"),command=create).pack(fill="x",padx=24,pady=24)
        localize_widget_tree(win)

    def open_legacy_import(self):
        if not self.is_admin():
            messagebox.showerror("Access denied", "Legacy GPA import is restricted to the Principal Administrator.", parent=self); return
        sid=self.active_sid()
        if not sid: messagebox.showwarning("Legacy import","Create or select a student first.",parent=self); return
        win=ctk.CTkToplevel(self); win.title(tr("Legacy import")); win.geometry("460x420"); win.resizable(False,False); win.transient(self); win.grab_set(); win.configure(fg_color=PREMIUM_UI["bg"])
        ctk.CTkLabel(win,text="Legacy GPA backfill",text_color=PREMIUM_UI["text"],font=self._font(20,"bold")).pack(anchor="w",padx=24,pady=(24,4))
        ctk.CTkLabel(win,text="Reconstruct historical grades to match a precise baseline.",text_color=PREMIUM_UI["muted"],font=self._font(10),wraplength=400,justify="left").pack(anchor="w",padx=24,pady=(0,18))
        ctk.CTkLabel(win,text="BASELINE GPA",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=24,pady=(8,4))
        baseline=ctk.CTkEntry(win,height=40,corner_radius=10,fg_color=PREMIUM_UI["surface2"],border_color=PREMIUM_UI["line"]); baseline.pack(fill="x",padx=24); baseline.insert(0,"3.2")
        ctk.CTkLabel(win,text="HISTORICAL LESSON COUNT",text_color=PREMIUM_UI["muted"],font=self._font(8,"bold",FONT_MONO)).pack(anchor="w",padx=24,pady=(16,4))
        count=ctk.CTkEntry(win,height=40,corner_radius=10,fg_color=PREMIUM_UI["surface2"],border_color=PREMIUM_UI["line"]); count.pack(fill="x",padx=24); count.insert(0,"12")
        def run():
            try:
                actual=self.model.legacy_backfill(sid,float(baseline.get().replace(",",".")),int(count.get())); win.destroy(); self.refresh_all(); messagebox.showinfo("Legacy import",f"Backfill complete. GPA = {actual:.4f}",parent=self)
            except Exception as exc: messagebox.showerror("Legacy import",tr_error(exc),parent=win)
        ctk.CTkButton(win,text="Run exact backfill",height=42,corner_radius=11,fg_color=PREMIUM_UI["cyan2"],hover_color="#1BB6E4",text_color="#071018",font=self._font(10,"bold"),command=run).pack(fill="x",padx=24,pady=24)
        localize_widget_tree(win)

    def run_clutch(self):
        sid=self.active_sid()
        if not sid: return
        try:
            target=float(self.target_var.get().replace(",",".")); result=self.analytics_engine.clutch_gpa_simulator(sid,target); self.projection_chart.set_result(result)
            needed=result.get("required_consecutive_tens"); text=(f"Student: {self.model.get_student(sid)['name']}\nCurrent weighted GPA: {result['current_gpa']:.4f}\nTarget: {result['target_gpa']:.2f}\n\n")
            if result.get("reachable"):
                text += f"Required consecutive flawless scores: {needed}\nProjected GPA at crossing: {result['projected_gpa']:.4f}\n"
            else:
                text += f"STRATEGIC ALERT\n{result.get('alert_code')}\nMaximum projected GPA: {result['projected_gpa']:.4f}\n"
            self.analytics_text.configure(state="normal"); self.analytics_text.delete("1.0","end"); self.analytics_text.insert("1.0",text); self.analytics_text.configure(state="disabled"); self.refresh_analytics(result)
        except Exception as exc: messagebox.showerror("Analytics",tr_error(exc),parent=self)

    def refresh_analytics(self,result=None):
        sid=self.active_sid()
        if not sid:
            for v in self.analytics_values.values(): v.configure(text="—")
            self.projection_chart.set_result(None); return
        gpa=self.model.weighted_gpa(sid); consistency=self.analytics_engine.calculate_consistency_rate(sid); impact=self.model.delinquency_impact(sid)
        if result is None:
            try: result=self.analytics_engine.clutch_gpa_simulator(sid,float(self.target_var.get().replace(",",".")))
            except Exception: result=None
        self.analytics_values["current"].configure(text=f"{gpa:.3f}")
        self.analytics_values["consistency"].configure(text=f"{consistency*100:.1f}%")
        needed=result.get("required_consecutive_tens") if result else None
        self.analytics_values["needed"].configure(text="∞" if result and not result.get("reachable") else str(needed if needed is not None else "—"))
        self.analytics_values["impact"].configure(text=f"-{impact.get('penalty_points',0):.3f}")
        if result: self.projection_chart.set_result(result)

    def on_exam_score(self,value):
        self.exam_score_var.set(float(value)); self.exam_score_label.configure(text=f"{int(round(float(value)))} / 100")

    def save_exam_score(self):
        if not self.can_manage_graduation():
            messagebox.showerror("Access denied", "Your account cannot modify graduation controls.", parent=self); return
        sid=self.active_sid()
        if not sid: return
        self.model.get_student(sid)["graduation_exam_score"]=int(round(self.exam_score_var.get())); self.model.store.save(); self.refresh_graduation(); self.set_status("Graduation exam score saved")

    def save_moderator_requests(self):
        if not self.can_manage_graduation():
            messagebox.showerror("Access denied", "Your account cannot modify moderator requests.", parent=self); self.refresh_graduation(); return
        self.model.settings["moderator_requests"]={k:bool(v.get()) for k,v in self.mod_vars.items()}; self.model.store.save()

    def refresh_graduation(self):
        sid=self.active_sid()
        if not sid:
            self.exam_slider.set(0); self.exam_score_label.configure(text="0 / 100"); summary=tr("No active student selected.")
        else:
            s=self.model.get_student(sid); score=int(s.get("graduation_exam_score",0)); self.exam_slider.set(score); self.exam_score_var.set(score); self.exam_score_label.configure(text=f"{score} / 100")
            summary=(tr(f"{s['name']}\n\nWeighted GPA      {self.model.weighted_gpa(sid):.3f}\nCurriculum        {self.model.progress(sid)*100:.1f}%\nGrade records     {self.model.total_grade_count(sid)}\nHomework skips    {s.get('homework_skips',0)}\nActive lesson     {self.model.active_lesson_id(sid) or 'COMPLETE'}\n"))
        self.grad_summary.configure(state="normal"); self.grad_summary.delete("1.0","end"); self.grad_summary.insert("1.0",summary); self.grad_summary.configure(state="disabled")

    def export_graduation_report(self):
        sid=self.active_sid()
        if not sid: return
        s=self.model.get_student(sid); path=filedialog.asksaveasfilename(parent=self,defaultextension=".html",filetypes=[(tr("HTML report"),"*.html")],initialfile=f"ACA_{s['name'].replace(' ','_')}_report.html")
        if not path: return
        phase_rows="".join(
            f"<tr><td>{html.escape(tr('Phase'))} {p}</td><td>{html.escape(tr(next(l['phase_name'] for l in CURRICULUM if l['phase']==p)))}</td><td>{self.model.phase_gpa(sid,p):.3f}</td></tr>"
            for p in range(1,8)
        )
        grade_rows=[]
        for l in CURRICULUM:
            grades=self.model.get_grades(sid,l["id"])
            if grades:
                vals=", ".join(f"{_fmt_grade(g['grade'])}×{g.get('weight_multiplier',1)}" for g in grades)
                grade_rows.append(f"<tr><td>{l['id']}</td><td>{html.escape(localize_lesson_name(l['name']))}</td><td>{html.escape(vals)}</td></tr>")
        report_title = tr("ACA Graduation Report")
        dossier_label = tr("Graduation dossier")
        report=f'''<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(report_title)}</title><style>body{{margin:0;background:#090D14;color:#F7FAFF;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}.page{{max-width:1050px;margin:40px auto;padding:42px;background:#101823;border:1px solid #26364A;border-radius:20px}}.brand{{color:#43D7FF;font-size:12px;font-weight:800;letter-spacing:2px}}h1{{font-size:40px;margin:10px 0 4px}}.meta{{color:#7F91A8}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0}}.k{{background:#151F2D;padding:18px;border:1px solid #26364A;border-radius:12px}}.k b{{display:block;font-size:24px;color:#55E6A5;margin-top:6px}}table{{width:100%;border-collapse:collapse;margin-top:14px}}th,td{{padding:11px;border-bottom:1px solid #26364A;text-align:left}}th{{color:#7F91A8;font-size:12px}}@media print{{body{{background:white;color:#111}}.page{{border:0;margin:0;background:white}}}}</style></head><body><div class="page"><div class="brand">ACA PLATFORM</div><h1>{html.escape(s['name'])}</h1><div class="meta">{html.escape(dossier_label)} • {html.escape(format_datetime_localized(datetime.now()))}</div><div class="kpis"><div class="k">{html.escape(tr('Weighted GPA'))}<b>{self.model.weighted_gpa(sid):.3f}</b></div><div class="k">{html.escape(tr('Completion'))}<b>{self.model.progress(sid)*100:.1f}%</b></div><div class="k">{html.escape(tr('Grades'))}<b>{self.model.total_grade_count(sid)}</b></div><div class="k">{html.escape(tr('Solo exam'))}<b>{int(s.get('graduation_exam_score',0))}/100</b></div></div><h2>{html.escape(tr('Phase performance'))}</h2><table><tr><th>{html.escape(tr('Phase'))}</th><th>{html.escape(tr('Module'))}</th><th>GPA</th></tr>{phase_rows}</table><h2>{html.escape(tr('Grade ledger'))}</h2><table><tr><th>ID</th><th>{html.escape(tr('Lesson'))}</th><th>{html.escape(tr('Grades'))}</th></tr>{''.join(grade_rows)}</table></div></body></html>'''
        with open(path,"w",encoding="utf-8") as f: f.write(report)
        self.set_status(f"Report exported: {path}")

    def generate_teacher_invite(self):
        if not self.is_admin():
            messagebox.showerror("Access denied", "Only the Principal Administrator can create teacher invitations.", parent=self); return
        phases=[p for p,v in self.phase_access_vars.items() if v.get()]
        try:
            code=self.teacher_manager.generate_invite_code(phases,self.teacher_label_entry.get().strip() or "Teacher"); self.generated_code.configure(text=code); self.refresh_access(); self.set_status("Teacher invite generated")
        except Exception as exc: messagebox.showerror("Teacher invite",tr_error(exc),parent=self)

    def refresh_access(self):
        if not hasattr(self, "invite_scroll"):
            return
        for child in self.invite_scroll.winfo_children():
            child.destroy()
        if not self.is_admin():
            ctk.CTkLabel(self.invite_scroll, text="Administrator access required", text_color=PREMIUM_UI["muted"], font=self._font(10)).pack(anchor="w", padx=8, pady=10)
            localize_widget_tree(self.invite_scroll)
            return

        ctk.CTkLabel(self.invite_scroll, text="TEACHER INVITES", text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=8, pady=(8, 4))
        items = list(self.teacher_manager.invite_db.items())
        items.sort(key=lambda kv: kv[1].get("creation_timestamp", 0), reverse=True)
        if not items:
            ctk.CTkLabel(self.invite_scroll, text="No invite codes yet", text_color=PREMIUM_UI["muted"], font=self._font(10)).pack(anchor="w", padx=8, pady=(4, 12))
        for code, rec in items:
            row = ctk.CTkFrame(self.invite_scroll, corner_radius=12, fg_color=PREMIUM_UI["surface2"])
            row.pack(fill="x", pady=5, padx=4)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(top, text=code, text_color=PREMIUM_UI["cyan"], font=self._font(11, "bold", FONT_MONO)).pack(side="left")
            enabled = bool(rec.get("is_enabled", True))
            activated = bool(rec.get("is_activated"))
            if activated:
                status, color = "USED", PREMIUM_UI["green"]
            elif not enabled:
                status, color = "DISABLED", PREMIUM_UI["pink"]
            else:
                status, color = "PENDING", PREMIUM_UI["amber"]
            ctk.CTkLabel(top, text=status, text_color=color, font=self._font(8, "bold", FONT_MONO)).pack(side="right")
            invite_created = format_datetime_localized(rec.get("creation_iso") or rec.get("creation_timestamp"))
            meta = f"{rec.get('teacher_label','Teacher')}  •  phases {', '.join(map(str, rec.get('authorized_phases', [])))}  •  {tr('Created')} {invite_created}"
            ctk.CTkLabel(row, text=meta, text_color=PREMIUM_UI["muted"], font=self._font(9)).pack(anchor="w", padx=12, pady=(0, 7))
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(fill="x", padx=12, pady=(0, 10))
            if not activated:
                ctk.CTkButton(
                    actions, text="Disable" if enabled else "Enable", width=74, height=30, corner_radius=10,
                    fg_color="#45202A" if enabled else "#173829", hover_color="#5A2835" if enabled else "#1F4D39",
                    font=self._font(8, "bold"),
                    command=lambda c=code, state=not enabled: self.toggle_invite(c, state),
                ).pack(side="left")
            ctk.CTkButton(
                actions, text="Reissue", width=74, height=30, corner_radius=10,
                fg_color=PREMIUM_UI["surface3"], hover_color=PREMIUM_UI["hover"],
                font=self._font(8, "bold"), command=lambda c=code: self.reissue_invite(c),
            ).pack(side="left", padx=(6, 0))

        ctk.CTkFrame(self.invite_scroll, height=1, fg_color=PREMIUM_UI["line"]).pack(fill="x", padx=6, pady=12)
        ctk.CTkLabel(self.invite_scroll, text="REGISTERED ACCOUNTS", text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=8, pady=(0, 4))
        accounts = sorted(self.auth_manager.list_accounts(), key=lambda a: (a.get("role", ""), a.get("display_name", "").casefold()))
        for account in accounts:
            row = ctk.CTkFrame(self.invite_scroll, corner_radius=12, fg_color=PREMIUM_UI["surface2"])
            row.pack(fill="x", pady=5, padx=4)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 2))
            role = account.get("role", "USER")
            role_color = PREMIUM_UI["cyan"] if role == "ADMIN" else PREMIUM_UI["violet"] if role == "TEACHER" else PREMIUM_UI["green"]
            ctk.CTkLabel(top, text=account.get("display_name") or account.get("username"), text_color=PREMIUM_UI["text"], font=self._font(10, "bold")).pack(side="left")
            ctk.CTkLabel(top, text=role, text_color=role_color, font=self._font(8, "bold", FONT_MONO)).pack(side="left", padx=(8, 0))
            active = bool(account.get("active", True))
            ctk.CTkLabel(top, text="ACTIVE" if active else "DISABLED", text_color=PREMIUM_UI["green"] if active else PREMIUM_UI["pink"], font=self._font(8, "bold", FONT_MONO)).pack(side="right")
            meta = f"@{account.get('username','')}"
            if role == "TEACHER":
                meta += f"  •  phases {', '.join(map(str, account.get('authorized_phases', [])))}"
            if role == "STUDENT" and account.get("student_id"):
                meta += f"  •  student {account.get('student_id')[-6:]}"
            if account.get("must_change_password"):
                meta += "  •  PASSWORD RESET REQUIRED"
            created_text = format_date_localized(account.get("created_at"), short=True)
            last_login_text = format_relative_date_localized(account.get("last_login_at")) if account.get("last_login_at") else tr("Never")
            meta += f"  •  {tr('Created')} {created_text}  •  {tr('Last login')} {last_login_text}"
            ctk.CTkLabel(row, text=meta, text_color=PREMIUM_UI["muted"], font=self._font(9), wraplength=650, justify="left").pack(anchor="w", padx=12, pady=(0, 7))

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(fill="x", padx=12, pady=(0, 10))
            uid = account.get("user_id")
            is_self = uid == self.auth_context.get("user_id")
            if not is_self:
                ctk.CTkButton(
                    actions, text="Role", width=62, height=30, corner_radius=10,
                    fg_color=PREMIUM_UI["surface3"], hover_color=PREMIUM_UI["hover"],
                    font=self._font(8, "bold"), command=lambda u=uid: self.open_role_change(u),
                ).pack(side="left")
                ctk.CTkButton(
                    actions, text="Reset password", width=104, height=30, corner_radius=10,
                    fg_color="#27314A", hover_color="#33405F", font=self._font(8, "bold"),
                    command=lambda u=uid: self.open_password_reset(u),
                ).pack(side="left", padx=(6, 0))
                action = "Disable" if active else "Enable"
                ctk.CTkButton(
                    actions, text=action, width=68, height=30, corner_radius=10,
                    fg_color="#45202A" if active else "#173829",
                    hover_color="#5A2835" if active else "#1F4D39",
                    font=self._font(8, "bold"),
                    command=lambda u=uid, state=not active: self.toggle_account(u, state),
                ).pack(side="right")
            else:
                ctk.CTkLabel(actions, text="Current session", text_color=PREMIUM_UI["cyan"], font=self._font(8, "bold", FONT_MONO)).pack(side="left")
        localize_widget_tree(self.invite_scroll)

    def toggle_invite(self, invite_code, enabled):
        try:
            self.teacher_manager.set_invite_enabled(invite_code, enabled)
            self.refresh_access()
            self.set_status("Invite enabled" if enabled else "Invite disabled")
        except Exception as exc:
            messagebox.showerror("Invite", tr_error(exc), parent=self)

    def reissue_invite(self, invite_code):
        try:
            new_code = self.teacher_manager.reissue_invite(invite_code)
            self.generated_code.configure(text=new_code)
            self.refresh_access()
            self.set_status(f"Invite reissued: {new_code}")
        except Exception as exc:
            messagebox.showerror("Invite", tr_error(exc), parent=self)

    def toggle_account(self, user_id, active):
        try:
            self.auth_manager.set_account_active(user_id, active, self.auth_context)
            self.refresh_access()
            self.set_status("Account enabled" if active else "Account disabled")
        except Exception as exc:
            messagebox.showerror("Account", tr_error(exc), parent=self)

    def open_role_change(self, user_id):
        account = next((a for a in self.auth_manager.list_accounts() if a.get("user_id") == user_id), None)
        if not account:
            messagebox.showerror("Role", "Account not found.", parent=self)
            return
        win = ctk.CTkToplevel(self)
        win.title(tr("Change account role"))
        win.geometry("500x430")
        win.resizable(False, False)
        win.configure(fg_color=PREMIUM_UI["bg"])
        win.transient(self)
        win.grab_set()
        card = ctk.CTkFrame(win, corner_radius=22, fg_color=PREMIUM_UI["surface"], border_width=1, border_color=PREMIUM_UI["card_border_soft"])
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(card, text="Change role", text_color=PREMIUM_UI["text"], font=self._font(19, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        ctk.CTkLabel(card, text=f"{account.get('display_name')}  •  @{account.get('username')}", text_color=PREMIUM_UI["muted"], font=self._font(9)).pack(anchor="w", padx=18, pady=(0, 14))
        roles = [role_display_value(role) for role in ("STUDENT", "TEACHER", "ADMIN")]
        role_var = tk.StringVar(value=role_display_value(account.get("role", "STUDENT")))
        selector = ctk.CTkSegmentedButton(card, values=roles, variable=role_var, height=38, corner_radius=11,
                                          fg_color=PREMIUM_UI["surface2"], selected_color=PREMIUM_UI["surface4"],
                                          selected_hover_color=PREMIUM_UI["hover"], unselected_color=PREMIUM_UI["surface2"],
                                          unselected_hover_color=PREMIUM_UI["hover"], font=self._font(9, "bold"))
        selector.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkLabel(card, text="TEACHER PHASE ACCESS", text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=18, pady=(2, 5))
        phase_frame = ctk.CTkFrame(card, fg_color="transparent")
        phase_frame.pack(fill="x", padx=18)
        current_phases = set(account.get("authorized_phases") or ([7] if account.get("role") != "ADMIN" else VALID_PHASES))
        phase_vars = {}
        for p in VALID_PHASES:
            var = tk.BooleanVar(value=p in current_phases)
            phase_vars[p] = var
            ctk.CTkCheckBox(phase_frame, text=tr(f"Phase {p}"), variable=var, width=100, checkbox_width=18, checkbox_height=18,
                            corner_radius=5, border_color=PREMIUM_UI["line"], fg_color=_phase_accent(p), hover_color=_phase_accent(p),
                            font=self._font(9)).grid(row=(p-1)//2, column=(p-1)%2, sticky="w", pady=5, padx=(0, 12))
        status = ctk.CTkLabel(card, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=420, justify="left")
        status.pack(anchor="w", padx=18, pady=(10, 0))
        def save_role():
            try:
                role = role_code_from_display(role_var.get())
                phases = [p for p, var in phase_vars.items() if var.get()] if role == "TEACHER" else None
                self.auth_manager.change_account_role(user_id, role, self.auth_context, phases)
                win.destroy()
                self.refresh_access()
                self.set_status("Account role updated")
            except Exception as exc:
                status.configure(text=tr_error(exc))
        ctk.CTkButton(card, text="Apply role", height=40, corner_radius=10, fg_color=PREMIUM_UI["cyan2"], hover_color="#1BB6E4",
                      text_color="#071018", font=self._font(10, "bold"), command=save_role).pack(fill="x", padx=18, pady=(16, 18))
        localize_widget_tree(win)
        attach_tooltip(selector, "role_selector")

    def open_password_reset(self, user_id):
        account = next((a for a in self.auth_manager.list_accounts() if a.get("user_id") == user_id), None)
        if not account:
            messagebox.showerror("Password reset", "Account not found.", parent=self)
            return
        win = ctk.CTkToplevel(self)
        win.title(tr("Force password reset"))
        win.geometry("500x360")
        win.resizable(False, False)
        win.configure(fg_color=PREMIUM_UI["bg"])
        win.transient(self)
        win.grab_set()
        card = ctk.CTkFrame(win, corner_radius=22, fg_color=PREMIUM_UI["surface"], border_width=1, border_color=PREMIUM_UI["card_border_soft"])
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(card, text="Force password reset", text_color=PREMIUM_UI["text"], font=self._font(19, "bold")).pack(anchor="w", padx=18, pady=(18, 2))
        ctk.CTkLabel(card, text=f"{account.get('display_name')}  •  @{account.get('username')}", text_color=PREMIUM_UI["muted"], font=self._font(9)).pack(anchor="w", padx=18, pady=(0, 12))
        ctk.CTkLabel(card, text="Temporary password", text_color=PREMIUM_UI["muted"], font=self._font(8, "bold", FONT_MONO)).pack(anchor="w", padx=18, pady=(4, 4))
        temp_var = tk.StringVar(value=(uuid.uuid4().hex[:10] + "A9"))
        entry = ctk.CTkEntry(card, textvariable=temp_var, height=40, corner_radius=12, fg_color=PREMIUM_UI["surface2"], border_width=1, border_color="#16486F", font=self._font(11, "bold", FONT_MONO))
        entry.pack(fill="x", padx=18)
        ctk.CTkLabel(card, text="The user will be forced to choose a new private password at the next sign-in.", text_color=PREMIUM_UI["muted"], font=self._font(9), wraplength=420, justify="left").pack(anchor="w", padx=18, pady=(9, 8))
        status = ctk.CTkLabel(card, text="", text_color=PREMIUM_UI["pink"], font=self._font(9), wraplength=420, justify="left")
        status.pack(anchor="w", padx=18, pady=(2, 0))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(16, 18))
        def regenerate():
            temp_var.set(uuid.uuid4().hex[:10] + "A9")
        def apply_reset():
            try:
                value = temp_var.get()
                self.auth_manager.admin_reset_password(user_id, value, self.auth_context, force_change=True)
                try:
                    self.clipboard_clear(); self.clipboard_append(value)
                except Exception:
                    pass
                win.destroy()
                self.refresh_access()
                self.set_status("Temporary password reset; copied to clipboard")
                messagebox.showinfo("Password reset", f"Temporary password:\n\n{value}\n\nIt has been copied to the clipboard. The user must change it at next sign-in.", parent=self)
            except Exception as exc:
                status.configure(text=tr_error(exc))
        ctk.CTkButton(buttons, text="Generate", width=92, height=40, corner_radius=12, fg_color=PREMIUM_UI["surface3"], hover_color=PREMIUM_UI["hover"], font=self._font(9, "bold"), command=regenerate).pack(side="left")
        ctk.CTkButton(buttons, text="Reset password", height=40, corner_radius=12, fg_color="#6C3349", hover_color="#82405A", font=self._font(9, "bold"), command=apply_reset).pack(side="right", fill="x", expand=True, padx=(8, 0))
        localize_widget_tree(win)
        attach_tooltip(entry, "temporary_password")

    def backup_database(self):
        if not self.is_admin():
            messagebox.showerror("Access denied", "Database backup is restricted to the Principal Administrator.", parent=self); return
        try:
            path=self.model.store.backup(); self.set_status(f"Backup created: {path}"); messagebox.showinfo("Backup",f"Backup created:\n{path}",parent=self)
        except Exception as exc: messagebox.showerror("Backup",tr_error(exc),parent=self)

    def refresh_student_combo(self):
        labels=[]; self.student_label_to_id={}
        allowed_ids = [self.auth_context.get("student_id")] if self.is_student() else list(self.model.students.keys())
        for sid in allowed_ids:
            s=self.model.students.get(sid)
            if not s: continue
            label=f"{s.get('name',sid)}  ·  {sid[-6:]}"; labels.append(label); self.student_label_to_id[label]=sid
        self.student_combo.configure(values=labels)
        active=self.active_sid()
        selected=next((lab for lab,si in self.student_label_to_id.items() if si==active),"")
        if selected:
            self.student_combo.set(selected)
        elif labels:
            first_sid = self.student_label_to_id[labels[0]]
            self._active_student_id = first_sid
            self.student_combo.set(labels[0])
        else:
            self._active_student_id = None
            self.student_combo.set(tr("No students"))

    def _set_live_sync_state(self, state, touch_time=False):
        """Update the live-sync badge using semantic status colors."""
        state = str(state or "ONLINE").upper()
        colors = {
            "ONLINE": PREMIUM_UI["green"],
            "SYNCING": PREMIUM_UI["amber"],
            "DELAYED": PREMIUM_UI["amber"],
            "ERROR": PREMIUM_UI["red"],
        }
        if state not in colors:
            state = "ERROR"
        color = colors[state]
        self._live_sync_state = state
        if touch_time:
            self._live_sync_last_success = datetime.now()
        if hasattr(self, "live_sync_label"):
            self.live_sync_label.configure(text=f"● {tr(state)}", text_color=color)
        if hasattr(self, "live_sync_badge"):
            self.live_sync_badge.configure(border_color=color)
        if hasattr(self, "live_sync_time_label"):
            if self._live_sync_last_success is None:
                text = tr("Last sync —")
            else:
                text = tr("Last sync ") + format_time_localized(self._live_sync_last_success, with_seconds=True)
            self.live_sync_time_label.configure(text=text)

    def manual_refresh_students(self):
        """Force a full disk reload and rebuild student-dependent UI state."""
        button = getattr(self, "refresh_students_button", None)
        try:
            self._set_live_sync_state("SYNCING")
            self._live_sync_syncing_until = datetime.now().timestamp() + 0.35
            if button is not None:
                button.configure(state="disabled", text="…")
            self.update_idletasks()
            if not self.model.store.force_reload():
                raise RuntimeError("Shared database is temporarily unavailable. Try again.")

            fresh_context = self.auth_manager.account_context(self.auth_context.get("user_id"))
            if fresh_context is None:
                self.logout_requested = True
                self.destroy()
                return
            self.auth_context = fresh_context

            if self.is_student():
                self._active_student_id = self.auth_context.get("student_id")
            elif self._active_student_id not in self.model.students:
                self._active_student_id = next(iter(self.model.students), None)

            self._live_sync_failures = 0
            self._live_sync_failure_started = None
            self.refresh_all()
            self._set_live_sync_state("ONLINE", touch_time=True)
            self.set_status(f"Students refreshed • {len(self.model.students)} loaded")
        except Exception as exc:
            self._live_sync_failures += 1
            if self._live_sync_failure_started is None:
                self._live_sync_failure_started = datetime.now().timestamp()
            self._set_live_sync_state("ERROR")
            messagebox.showerror("Refresh students", tr_error(exc), parent=self)
            self.set_status("Manual refresh failed")
        finally:
            if button is not None and self.winfo_exists():
                button.configure(state="normal", text="↻")

    def refresh_overview(self):
        sid=self.active_sid(); self.hero.redraw(); self.gpa_chart.draw_chart()
        if not sid:
            for v in self.metric_values.values(): v.configure(text="—")
            self.sidebar_student_name.configure(text=tr("No student")); self.sidebar_student_meta.configure(text=tr("Create a profile"))
            for bar,val in self.phase_rows.values(): bar.set(0); val.configure(text="—")
            return
        s=self.model.get_student(sid); gpa=self.model.weighted_gpa(sid); grades=self.model.total_grade_count(sid); lessons=sum(1 for l in CURRICULUM if self.model.get_grades(sid,l["id"])); consistency=self.analytics_engine.calculate_consistency_rate(sid)
        self.metric_values["gpa"].configure(text=f"{gpa:.3f}"); self.metric_values["grades"].configure(text=str(grades)); self.metric_values["lessons"].configure(text=f"{lessons}/120"); self.metric_values["consistency"].configure(text=f"{consistency*100:.1f}%")
        self.sidebar_student_name.configure(text=s.get("name",tr("Student"))); self.sidebar_student_meta.configure(text=f"GPA {gpa:.2f}  •  {localized_grade_count(grades)}")
        for p,(bar,val) in self.phase_rows.items():
            pg=self.model.phase_gpa(sid,p); bar.set(clamp(pg/10.0,0.0,1.0)); val.configure(text=f"{pg:.2f}" if any(self.model.get_grades(sid,l["id"]) for l in CURRICULUM if l["phase"]==p) else "—")

    def refresh_all(self):
        self.refresh_student_combo(); self.refresh_overview(); self.grade_grid.render(); self.refresh_analytics(); self.refresh_graduation(); self.refresh_access()
        if self.inspector_lesson_id: self.set_inspector_lesson(self.inspector_lesson_id)
        self._refresh_topbar_badges(); self._refresh_journal_chrome()
        localize_widget_tree(self)

    def live_sync_tick(self):
        """Pull cross-window changes with sub-second latency and expose real sync health."""
        now_ts = datetime.now().timestamp()
        try:
            changed = self.model.store.reload_if_changed()
            self._live_sync_failures = 0
            self._live_sync_failure_started = None
            if changed:
                self._set_live_sync_state("SYNCING")
                self._live_sync_syncing_until = now_ts + 0.35
                fresh_context = self.auth_manager.account_context(self.auth_context.get("user_id"))
                if fresh_context is None:
                    self.logout_requested = True
                    self.destroy()
                    return
                self.auth_context = fresh_context
                if self.is_student():
                    self._active_student_id = self.auth_context.get("student_id")
                elif self._active_student_id not in self.model.students:
                    self._active_student_id = next(iter(self.model.students), None)
                self.refresh_all()
                self._live_sync_last_success = datetime.now()
                if hasattr(self, "live_sync_time_label"):
                    self.live_sync_time_label.configure(text=tr("Last sync ") + format_time_localized(self._live_sync_last_success, with_seconds=True))
                self.set_status("Live sync • database updated")
            elif now_ts >= self._live_sync_syncing_until:
                self._set_live_sync_state("ONLINE")
        except Exception:
            self._live_sync_failures += 1
            if self._live_sync_failure_started is None:
                self._live_sync_failure_started = now_ts
            outage = now_ts - self._live_sync_failure_started
            if outage >= 3.0:
                self._set_live_sync_state("ERROR")
            elif self._live_sync_failures >= 3:
                self._set_live_sync_state("DELAYED")
            # A single transient collision remains visually ONLINE to avoid flicker.
        if self.winfo_exists():
            self._live_sync_job = self.after(getattr(self.model.store, "poll_interval_ms", 120), self.live_sync_tick)

    def autosave_tick(self):
        # Retained for backward compatibility. Mutations save transactionally at
        # their source; periodic whole-database saves are unsafe with many windows.
        return None

    def on_close(self):
        if getattr(self, "_live_sync_job", None):
            try:
                self.after_cancel(self._live_sync_job)
            except Exception:
                pass
        self.destroy()


class AcademyController:
    def __init__(self):
        self.server_url = load_server_url()
        if self.server_url:
            self.store = ServerDataStore(self.server_url)
            self.model = AcademyModel(self.store)
            self.auth = ServerAuthenticationManager(self.store, self.model)
        elif _env_truthy("ACA_LOCAL_MODE"):
            self.store = DataStore(DB_FILE)
            self.model = AcademyModel(self.store)
            self.auth = AuthenticationManager(self.store, self.model)
        else:
            raise RuntimeError(
                "ACA server URL is unavailable. Local database fallback is disabled in production."
            )

    def run(self):
        if ctk is None:
            root=tk.Tk(); root.withdraw(); messagebox.showerror("Missing UI dependency","ACA Platform requires CustomTkinter.\n\nInstall once with:\n/usr/local/bin/python3 -m pip install customtkinter pillow"); root.destroy(); return
        context = None
        resume = getattr(self.auth, "try_resume_session", None)
        if callable(resume):
            try:
                context = resume()
            except Exception:
                context = None
        while True:
            if not context:
                gateway=AuthGateway(self.auth)
                gateway.mainloop()
                context=gateway.result
                if not context:
                    return
            app=AcademyApp(self.model,context,self.auth)
            app.mainloop()
            if not app.logout_requested:
                return
            context = None


def main():
    AcademyController().run()


if __name__ == "__main__":
    main()
