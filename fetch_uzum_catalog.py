from seleniumbase import SB
import json
import re


def fetch_catalog():
    print("Starting browser for Uzum Tezkor catalog...")
    with SB(uc=True, headless=False) as sb:
        sb.open("https://www.uzumtezkor.uz/ru")

        print("\n*** ВНИМАНИЕ! Выберите адрес доставки на карте! ***\n")
        print("Скрипт подождет 20 секунд, а затем начнет скроллить вниз.\n")

        js_interceptor = """
        window.uzumResponses = [];
        
        const origFetch = window.fetch;
        window.fetch = async (...args) => {
            const res = await origFetch(...args);
            res.clone().text().then(text => {
                if (text.includes('vendor') || text.includes('restaurant') || text.includes('alias')) {
                    window.uzumResponses.push(text);
                }
            }).catch(e => {});
            return res;
        };
        
        const origOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function() {
            this.addEventListener('load', function() {
                try {
                    const text = this.responseText;
                    if (text.includes('vendor') || text.includes('restaurant') || text.includes('alias')) {
                        window.uzumResponses.push(text);
                    }
                } catch(e) {}
            });
            origOpen.apply(this, arguments);
        };
        """
        sb.execute_script(js_interceptor)

        # Ждем 20 секунд, чтобы пользователь выбрал адрес
        for i in range(10):
            print(f"Ожидание выбора адреса... {20 - i * 2} сек.")
            sb.sleep(2)

        print("\nНачинаю скроллинг страницы! Пожалуйста, не трогайте браузер.")

        for i in range(100):
            sb.execute_script("window.scrollBy(0, 3000);")
            sb.sleep(1.5)
            if i % 10 == 0:
                print(f"Скроллинг... Шаг {i}/100")

        print("\nСкроллинг завершен. Извлекаю данные...")

        # Получаем все перехваченные ответы
        responses = sb.execute_script("return window.uzumResponses;") or []

        # Также берем весь HTML на всякий случай
        html = sb.execute_script("return document.body.innerHTML;") or ""

        full_text = html + "\n" + "\n".join(responses)

        # Ищем возможные алиасы/slug/ID ресторанов
        # Паттерн 1: "alias":"что-то"
        aliases = re.findall(r'"alias"\s*:\s*"([^"]+)"', full_text)
        # Паттерн 2: "slug":"что-то"
        slugs = re.findall(r'"slug"\s*:\s*"([^"]+)"', full_text)
        # Паттерн 3: прямые ссылки /restaurant/что-то
        links1 = re.findall(r'/restaurant/([^"\'\\s\\?]+)', full_text)
        links2 = re.findall(r'/restaurants/([^"\'\\s\\?]+)', full_text)

        # Объединяем все найденное
        all_ids = set(aliases + slugs + links1 + links2)

        # Фильтруем мусор
        valid_ids = []
        for vid in all_ids:
            # ID не должен содержать слэши, скобки или быть слишком коротким
            if len(vid) > 2 and "/" not in vid and "{" not in vid and "<" not in vid:
                valid_ids.append(vid)

        if valid_ids:
            final_urls = [
                f"https://www.uzumtezkor.uz/ru/restaurants/{vid}" for vid in valid_ids
            ]
            with open("uzum_catalog.json", "w", encoding="utf-8") as f:
                json.dump(final_urls, f, indent=4)
            print(
                f"\nУСПЕХ! Сохранено {len(final_urls)} ресторанов в uzum_catalog.json!"
            )
        else:
            print(
                "\nОШИБКА: Скрипт не смог найти ID ресторанов. Узум полностью изменил логику."
            )

        # ВСЕГДА сохраняем дамп для дебага
        with open("uzum_debug_dump.txt", "w", encoding="utf-8") as f:
            f.write(full_text)
        print("Дамп сохранен в uzum_debug_dump.txt")


if __name__ == "__main__":
    fetch_catalog()
