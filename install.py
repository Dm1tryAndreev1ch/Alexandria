#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для установки всех необходимых библиотек проекта
"""

import os
import sys
import subprocess
import platform

def print_header():
    """Вывод заголовка"""
    print("=" * 60)
    print("Установка зависимостей проекта Alexandria")
    print("=" * 60)
    print()

def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Ошибка: требуется Python 3.8 или выше")
        print(f"   Текущая версия: {version.major}.{version.minor}.{version.micro}")
        sys.exit(1)
    print(f"✅ Python версия: {version.major}.{version.minor}.{version.micro}")
    return version

def check_pip():
    """Проверка наличия pip"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ pip найден: {result.stdout.strip()}")
            return True
        else:
            print("❌ pip не найден")
            return False
    except Exception as e:
        print(f"❌ Ошибка при проверке pip: {e}")
        return False

def upgrade_pip():
    """Обновление pip до последней версии"""
    print("\n📦 Обновление pip...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("✅ pip обновлен")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Предупреждение: не удалось обновить pip: {e}")
        return False

def read_requirements():
    """Чтение requirements.txt"""
    requirements_file = "requirements.txt"
    if not os.path.exists(requirements_file):
        print(f"❌ Ошибка: файл {requirements_file} не найден")
        sys.exit(1)
    
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = []
        for line in f:
            line = line.strip()
            # Пропускаем пустые строки и комментарии
            if line and not line.startswith('#'):
                # Убираем условия платформы для упрощения
                if ';' in line:
                    line = line.split(';')[0].strip()
                requirements.append(line)
    
    return requirements

def install_package(package):
    """Установка одного пакета"""
    try:
        print(f"   Установка: {package}...", end=' ', flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌")
        print(f"      Ошибка: {e.stderr}")
        return False

def install_requirements(requirements):
    """Установка всех зависимостей"""
    print(f"\n📦 Установка {len(requirements)} зависимостей...\n")
    
    failed_packages = []
    successful_packages = []
    
    for i, package in enumerate(requirements, 1):
        print(f"[{i}/{len(requirements)}] ", end='')
        if install_package(package):
            successful_packages.append(package)
        else:
            failed_packages.append(package)
    
    print("\n" + "=" * 60)
    print("Результаты установки:")
    print("=" * 60)
    print(f"✅ Успешно установлено: {len(successful_packages)}")
    print(f"❌ Ошибок: {len(failed_packages)}")
    
    if failed_packages:
        print("\n⚠️  Не удалось установить следующие пакеты:")
        for package in failed_packages:
            print(f"   - {package}")
        print("\nПопробуйте установить их вручную:")
        print(f"   pip install {' '.join(failed_packages)}")
        return False
    
    return True

def main():
    """Основная функция"""
    # Настройка кодировки для Windows
    if platform.system() == 'Windows':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print_header()
    
    # Проверка версии Python
    check_python_version()
    
    # Проверка pip
    if not check_pip():
        print("\n❌ pip не найден. Установите pip и попробуйте снова.")
        sys.exit(1)
    
    # Обновление pip
    upgrade_pip()
    
    # Чтение requirements.txt
    print("\n📄 Чтение requirements.txt...")
    requirements = read_requirements()
    print(f"✅ Найдено {len(requirements)} зависимостей")
    
    # Установка зависимостей
    success = install_requirements(requirements)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ Все зависимости успешно установлены!")
        print("=" * 60)
        print("\nТеперь вы можете запустить приложение:")
        print("   python main.py")
        return 0
    else:
        print("\n" + "=" * 60)
        print("⚠️  Установка завершена с ошибками")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Установка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

