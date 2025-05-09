@echo off
chcp 65001 > nul
setlocal ENABLEDELAYEDEXPANSION

REM --- Настройки ---
set PYTHON_EXE=python
set VENV_NAME=.venv
set REQUIREMENTS_FILE=requirements.txt
set MAIN_SCRIPT=main_cli.py

REM --- Цвета для вывода (опционально, может не работать во всех версиях CMD) ---
REM Коды цветов взяты из стандартных возможностей CMD через ANSI-эскейп последовательности,
REM которые chcp 65001 (UTF-8) должен поддерживать в современных Windows.
REM Если цвета не работают, можно просто убрать переменные и их использование.
set "COLOR_INFO=\033[96m"    REM Светло-голубой (Cyan)
set "COLOR_SUCCESS=\033[92m" REM Светло-зеленый
set "COLOR_WARNING=\033[93m" REM Желтый
set "COLOR_ERROR=\033[91m"   REM Красный
set "COLOR_RESET=\033[0m"    REM Сброс цвета

echo %COLOR_INFO%--- Настройка окружения и запуск Видеомонтажера CLI ---%COLOR_RESET%
echo.

REM --- 1. Проверка Python ---
echo %COLOR_INFO%[1/4] Проверка наличия Python...%COLOR_RESET%
%PYTHON_EXE% --version > nul 2>&1
IF ERRORLEVEL 1 (
    echo %COLOR_ERROR%Ошибка: Python не найден.%COLOR_RESET%
    echo Пожалуйста, установите Python 3.7+ с официального сайта python.org
    echo %COLOR_WARNING%Не забудьте отметить "Add Python to PATH" при установке!%COLOR_RESET%
    pause
    exit /b 1
)
echo %COLOR_SUCCESS%Python найден.%COLOR_RESET%
echo.

REM --- 2. Проверка FFmpeg (косвенная) ---
echo %COLOR_INFO%[2/4] Напоминание о FFmpeg...%COLOR_RESET%
echo %COLOR_WARNING%Для работы скрипта необходим FFmpeg.%COLOR_RESET%
echo Убедитесь, что FFmpeg установлен и:
echo   а) его путь добавлен в системную переменную PATH, ИЛИ
echo   б) файлы ffmpeg.exe и ffprobe.exe находятся в той же папке, что и %MAIN_SCRIPT%.
echo Скачать FFmpeg можно, например, с gyan.dev (ищите "essentials" или "full" build).
echo.

REM --- 3. Создание/проверка виртуального окружения и установка зависимостей ---
echo %COLOR_INFO%[3/4] Настройка виртуального окружения и установка пакетов...%COLOR_RESET%
IF NOT EXIST "%VENV_NAME%\Scripts\activate.bat" (
    echo Создание виртуального окружения "%VENV_NAME%"...
    %PYTHON_EXE% -m venv %VENV_NAME%
    IF ERRORLEVEL 1 (
        echo %COLOR_ERROR%Ошибка: Не удалось создать виртуальное окружение.%COLOR_RESET%
        pause
        exit /b 1
    )
    echo %COLOR_SUCCESS%Виртуальное окружение создано.%COLOR_RESET%
) ELSE (
    echo %COLOR_SUCCESS%Виртуальное окружение "%VENV_NAME%" уже существует.%COLOR_RESET%
)

echo Активация окружения и установка/проверка зависимостей из %REQUIREMENTS_FILE%...
call "%VENV_NAME%\Scripts\activate.bat"
pip install -r %REQUIREMENTS_FILE%
IF ERRORLEVEL 1 (
    echo %COLOR_ERROR%Ошибка при установке зависимостей из %REQUIREMENTS_FILE%.%COLOR_RESET%
    echo Проверьте файл и ваше интернет-соединение.
    pause
    exit /b 1
)
echo %COLOR_SUCCESS%Зависимости успешно установлены/проверены.%COLOR_RESET%
echo.

REM --- 4. Запуск основного скрипта ---
echo %COLOR_INFO%[4/4] Подготовка к запуску скрипта %MAIN_SCRIPT%...%COLOR_RESET%
echo.
echo Пожалуйста, подготовьте ваши папки и файлы:
echo   - Папка с видео (например, input_videos)
echo   - Папка с аудио (например, input_audio)
echo   - Файл субтитров .ASS (например, input_subtitles\my_script.ass)
echo   - Папка для сохранения результатов (например, output_videos)
echo.
echo Пример команды для запуска (замените пути на свои):
echo   %PYTHON_EXE% %MAIN_SCRIPT% --video_dir ./input_videos --audio_dir ./input_audio --subtitle_ass_file ./input_subtitles/my_script.ass --output_dir ./output_videos -n 1
echo.

REM Запрос аргументов у пользователя (можно сделать более дружелюбным)
set "VIDEO_DIR_DEFAULT=./input_videos"
set "AUDIO_DIR_DEFAULT=./input_audio"
set "SUB_FILE_DEFAULT=./input_subtitles/script.ass"
set "OUTPUT_DIR_DEFAULT=./output_videos"
set "NUM_MONTAGES_DEFAULT=1"
set "MAX_DUR_DEFAULT=0"
set "MIN_DUR_DEFAULT=0"

echo Введите параметры или нажмите Enter для использования значений по умолчанию.
set /p VIDEO_DIR_USER="Папка с видео [%VIDEO_DIR_DEFAULT%]: "
set /p AUDIO_DIR_USER="Папка с аудио [%AUDIO_DIR_DEFAULT%]: "
set /p SUB_FILE_USER="Файл субтитров .ASS [%SUB_FILE_DEFAULT%]: "
set /p OUTPUT_DIR_USER="Папка для сохранения [%OUTPUT_DIR_DEFAULT%]: "
set /p NUM_MONTAGES_USER="Количество монтажей [%NUM_MONTAGES_DEFAULT%]: "
set /p MAX_DUR_USER="Макс. длительность (сек, 0=авто) [%MAX_DUR_DEFAULT%]: "
set /p MIN_DUR_USER="Мин. длительность (сек, 0=нет) [%MIN_DUR_DEFAULT%]: "

IF "%VIDEO_DIR_USER%"=="" SET "VIDEO_DIR_USER=%VIDEO_DIR_DEFAULT%"
IF "%AUDIO_DIR_USER%"=="" SET "AUDIO_DIR_USER=%AUDIO_DIR_DEFAULT%"
IF "%SUB_FILE_USER%"=="" SET "SUB_FILE_USER=%SUB_FILE_DEFAULT%"
IF "%OUTPUT_DIR_USER%"=="" SET "OUTPUT_DIR_USER=%OUTPUT_DIR_DEFAULT%"
IF "%NUM_MONTAGES_USER%"=="" SET "NUM_MONTAGES_USER=%NUM_MONTAGES_DEFAULT%"
IF "%MAX_DUR_USER%"=="" SET "MAX_DUR_USER=%MAX_DUR_DEFAULT%"
IF "%MIN_DUR_USER%"=="" SET "MIN_DUR_USER=%MIN_DUR_DEFAULT%"

set "FINAL_COMMAND=%PYTHON_EXE% %MAIN_SCRIPT% --video_dir "%VIDEO_DIR_USER%" --audio_dir "%AUDIO_DIR_USER%" --subtitle_ass_file "%SUB_FILE_USER%" --output_dir "%OUTPUT_DIR_USER%" --num_montages %NUM_MONTAGES_USER% --max_duration %MAX_DUR_USER% --min_duration %MIN_DUR_USER%"

echo.
echo %COLOR_INFO%Выполняется команда:%COLOR_RESET%
echo %FINAL_COMMAND%
echo.

%FINAL_COMMAND%

echo.
echo %COLOR_SUCCESS%--- Работа скрипта завершена ---%COLOR_RESET%
pause
exit /b 0