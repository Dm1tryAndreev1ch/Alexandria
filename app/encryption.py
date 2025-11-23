"""Модуль для шифрования персональных данных"""
from cryptography.fernet import Fernet
import os
import base64
import hashlib
from flask import current_app


def get_encryption_key():
    """Получение ключа шифрования из конфигурации или генерация нового"""
    try:
        key = current_app.config.get('ENCRYPTION_KEY')
        
        if not key:
            # Генерируем ключ из SECRET_KEY
            secret_key = current_app.config.get('SECRET_KEY', 'default-secret-key-change-me')
            # Используем SHA256 для получения 32 байт
            key_bytes = hashlib.sha256(secret_key.encode('utf-8')).digest()
            # Кодируем в base64 для Fernet
            key = base64.urlsafe_b64encode(key_bytes)
        else:
            if isinstance(key, str):
                key = key.encode('utf-8')
        
        return key
    except RuntimeError:
        # Если нет контекста приложения, используем дефолтный ключ
        secret_key = os.getenv('SECRET_KEY', 'default-secret-key-change-me')
        key_bytes = hashlib.sha256(secret_key.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(key_bytes)


def encrypt_data(data: str) -> str:
    """Шифрование данных"""
    if not data:
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        print(f"Error encrypting data: {e}")
        # В случае ошибки возвращаем исходные данные (для совместимости)
        return data


def decrypt_data(encrypted_data: str) -> str:
    """Расшифровка данных"""
    if not encrypted_data:
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_data.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"Error decrypting data: {e}")
        # В случае ошибки возвращаем исходные данные (возможно, не зашифровано)
        return encrypted_data

