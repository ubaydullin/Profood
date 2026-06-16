import os
import time
from seleniumbase import SB


def setup_auth():
    print("=" * 50)
    print("ИНСТРУКЦИЯ:")
    print("Сейчас откроется браузер.")
    print("1. Введите адрес доставки в Ташкенте для Uzum Tezkor.")
    print("2. Прокрутите ленту немного вниз, чтобы убедиться, что рестораны появились.")
    print("3. Сделайте то же самое на вкладке Яндекс Еды (появится позже).")
    print(
        "Данные сохранятся, и после этого сервер сможет парсить всё в фоновом режиме."
    )
    print("=" * 50)
    print("Запуск через 3 секунды...")
    time.sleep(3)

    # We use a specific persistent directory for cookies and session
    user_data_dir = os.path.join(os.path.dirname(__file__), "browser_data")

    with SB(uc=True, headless=False, user_data_dir=user_data_dir) as sb:
        print("\n--- Открываем Uzum Tezkor ---")
        sb.uc_open_with_reconnect("https://www.uzumtezkor.uz/ru", 5)
        print("Пожалуйста, установите адрес доставки на сайте Uzum Tezkor.")
        print(
            "У вас есть 60 секунд. Как только рестораны появятся в ленте, можете переходить в консоль."
        )

        # Wait for user to interact
        sb.sleep(60)

        print("\n--- Открываем Яндекс Еду ---")
        sb.uc_open_with_reconnect("https://eats.yandex.com/ru/tashkent", 5)
        print("Пожалуйста, установите адрес доставки на Яндекс Еде.")
        print("У вас есть 60 секунд. Убедитесь, что лента ресторанов загрузилась.")

        sb.sleep(60)

    print("\n✅ Сессия успешно сохранена! Теперь вы можете запустить бота (main.py).")


if __name__ == "__main__":
    setup_auth()
