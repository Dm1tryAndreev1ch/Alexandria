# Настройка доступа к MySQL

## Проблема

Ошибка: `Access denied for user 'delldev_devoniyolabuser'@'localhost' to database 'delldev_devoniyolab'`

Это означает, что пользователь MySQL не имеет прав доступа к указанной базе данных.

## Решение

### Вариант 1: Предоставить права пользователю (рекомендуется)

Подключитесь к MySQL как root или администратор:

```bash
mysql -u root -p
```

Затем выполните следующие команды:

```sql
-- Предоставить все права на базу данных
GRANT ALL PRIVILEGES ON delldev_devoniyolab.* TO 'delldev_devoniyolabuser'@'localhost';

-- Или если база данных еще не создана, сначала создайте её:
CREATE DATABASE IF NOT EXISTS delldev_devoniyolab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON delldev_devoniyolab.* TO 'delldev_devoniyolabuser'@'localhost';

-- Применить изменения
FLUSH PRIVILEGES;
```

### Вариант 2: Проверить правильность DATABASE_URL

Убедитесь, что в переменной окружения `DATABASE_URL` указаны правильные данные:

```bash
# Формат для MySQL с PyMySQL:
DATABASE_URL=mysql+pymysql://delldev_devoniyolabuser:password@localhost:3306/delldev_devoniyolab

# Или с mysql-connector:
DATABASE_URL=mysql+mysqlconnector://delldev_devoniyolabuser:password@localhost:3306/delldev_devoniyolab
```

**Важно:** Замените `password` на реальный пароль пользователя.

### Вариант 3: Создать базу данных и пользователя заново

Если у вас есть права root:

```sql
-- Создать базу данных
CREATE DATABASE delldev_devoniyolab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Создать пользователя (если еще не создан)
CREATE USER IF NOT EXISTS 'delldev_devoniyolabuser'@'localhost' IDENTIFIED BY 'your_password';

-- Предоставить права
GRANT ALL PRIVILEGES ON delldev_devoniyolab.* TO 'delldev_devoniyolabuser'@'localhost';

-- Применить изменения
FLUSH PRIVILEGES;
```

### Вариант 4: Использовать существующую базу данных

Если база данных уже существует, но с другим именем, обновите `DATABASE_URL`:

```bash
# Например, если база данных называется 'delldev_oniyolab':
DATABASE_URL=mysql+pymysql://delldev_devoniyolabuser:password@localhost:3306/delldev_oniyolab
```

## Проверка

После настройки прав проверьте подключение:

```bash
mysql -u delldev_devoniyolabuser -p delldev_devoniyolab
```

Если подключение успешно, значит права настроены правильно.

## Применение миграций

После настройки доступа к базе данных примените миграции:

```bash
flask db upgrade
```

## Для cPanel / Plesk

Если вы используете панель управления хостингом (cPanel, Plesk):

1. Зайдите в раздел "MySQL Databases" или "Базы данных"
2. Убедитесь, что база данных `delldev_devoniyolab` существует
3. Убедитесь, что пользователь `delldev_devoniyolabuser` добавлен к этой базе данных
4. Проверьте, что пользователю предоставлены все права (ALL PRIVILEGES)

## Важные замечания

- Убедитесь, что пароль в `DATABASE_URL` правильный
- Проверьте, что имя базы данных совпадает с тем, что указано в панели управления
- Для продакшена используйте отдельного пользователя с ограниченными правами (только для этой базы данных)

