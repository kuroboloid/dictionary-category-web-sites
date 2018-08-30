import psycopg2
import os
import re
import pandas as pd
from urllib.request import urlopen
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer

DATABASE = 'test_database'
USER = 'postgres'

# База данных (database).
#     Таблицы:
#         category (категории веб-страниц):
#             id_c - порядковый номер категории;
#             category - наименование.
#         urls (адреса веб-страниц)
#             id_url - порядковый номер адреса веб-страницы;
#             url - адрес веб-страницы.
#         tags_data (данные тегов с веб-страниц)
#             id_url - порядковый номер адреса веб-страницы;
#             tag - тег HTML-структуры веб-страницы;
#             data - данные тега.
#         dictionary (словарь по категориям)
#             category - наименование категории;
#             word - слово;
#             tfidf - вес слова.


def сheck_uniq_url(url):
    """Проверить, не сохранен ли в таблице веб-адрес.

    Параметр:
    url - string
        Адрес веб-страницы.
    Выход:
    boolean (True - не сохранен, False - уже имеется)
    """
    cursor.execute('SELECT * FROM public.urls')
    row = cursor.fetchone()
    while row is not None:
        if (url == row[1]):
            return False
        row = cursor.fetchone()
    return True

def urls_to_bd(file_name, id_url, id_lim, id_cat):
    """Занести адреса-веб страниц в БД из файла.

    Параметры:
    file_name - string
        Имя файла.
    """
    with open(file_name, 'r') as fp:
        for url_row in fp:
            url_row = url_row.rstrip()
            if id_url < id_lim:
                url_row = re.sub('(\')', "", url_row)
                if url_row.find("http://") == -1:
                    url_row = "http://" + url_row
                if (сheck_uniq_url(url_row)):
                    try:
                        urlopen(url_row, timeout=1)
                        cursor.execute("INSERT INTO public.urls (id_c, id_url, url) "
                                       "VALUES ('%d', '%d','%s')" % (id_cat, id_url, url_row))  # занесение URL из файлов в БД
                        conn.commit()
                        id_url += 1
                    except:
                        pass
    return id_url

def open_directory(dir_name):
    """Прочитать адреса веб-страниц в БД из внешних файлов в директории.

    Параметры:
    dir_name - string
        Имя директории.
    """
    cursor.execute(' TRUNCATE TABLE "category"')                   # Очистка таблиц.
    cursor.execute(' TRUNCATE TABLE "urls"')
    id_cat = 1
    id_url = 1
    lim = 5
    id_lim = lim
    list_dir = os.listdir(dir_name)             # Открыть корневую папку
    for dir in list_dir:                        # Открыть папку категории
        categ = dir                             # Имя категории = имя папки
        dir = dir_name + '/' + dir
        for file in os.listdir(dir):
            file_name = dir + '/' + file        # Имя файла.
            if file_name.find("/urls") != -1:   # Если файл с именем urls существует
                # Занесение id и категорий в БД.
                cursor.execute("INSERT INTO public.category (id_c, category) VALUES ('%d','%s')" % (
                    id_cat, categ))
                conn.commit()
                id_url = urls_to_bd(file_name, id_url, id_lim, id_cat)
                id_lim = id_url+lim
                id_cat += 1                     # id категории


def get_html(url_adrr):
    """получить полный html текст страницы.

    Параметр:
    url_adrr - string
        Адрес веб-страницы.

    Выход:
    HTML - string
        Структура веб-страницы.
    """
    try:
        url =  urlopen(url_adrr, timeout=2)
        HTML = url.read()                           # Получить html страницы.
        HTML= HTML.decode("UTF8")                   # Изменение кодировки в HTML-коде.
        HTML = re.sub('(\')', "\'\'", HTML)         # Замена ' на '' в HTML.
    except:
        return None
    return HTML


def get_tags(html_tags):
    """Получить информацию из значимых тегов на веб-страницы.

    Пааметр:
    html_tags - pd.Series
        Таблица с наименованями html-тегов.
    """
    cursor.execute(' TRUNCATE TABLE "tags_data"')
    cursor.execute('SELECT * FROM "urls"')
    cursor2 = conn.cursor()
    u = cursor.fetchone()
    while u is not None:
        id_url = u[1]                                             # Индекс веб-страницы.
        url_adrr = u[2]                                           # Адрес веб-страницы.
        HTML = get_html(url_adrr)
        if HTML is not None:
            soup = BeautifulSoup(HTML, 'html.parser')             # Получаем HTML страницы.
            for tag in html_tags[0].values:
                links = soup.find_all(tag)                        # Весь текст найденный по конкретному тегу.
                if (len(links)) != 0:
                    if tag != 'img':                              # Для всех тегов.
                        ht = re.sub('(\')', "\'\'", links[0].get_text())
                        # Добавление в таблицу text текста по тегам из HTML
                        cursor2.execute("INSERT INTO public.tags_data (id_url, tag, data) "
                                            "VALUES ('%s','%s','%s')" % (id_url, tag, ht))
                        conn.commit()
                    else:
                                                                   # Для тега img.
                        ht = re.sub('(\')', "\'\'", links[0].get('src'))
                        cursor2.execute("INSERT INTO public.tags_data (id_url, tag, data) "
                                        "VALUES ('%s','%s','%s')" % (id_url, tag, ht))
                        conn.commit()
        u = cursor.fetchone()
    cursor2.close()

def get_matrix_tfidf():
    cursor.execute('TRUNCATE TABLE "dictionary"')
    cursor.execute('SELECT category FROM "category"')
    categories = [cat[0] for cat in cursor.fetchall()]             # Список всех категорий.
    cat_count = len(categories)                                    # Количество категорий.
    data = list()
    data.extend([[] for i in range(cat_count)])
    cursor.execute('SELECT id_url, data FROM public.tags_data')
    cursor2 = conn.cursor()
    text = cursor.fetchone()
    while text is not None:
        id = text[0]
        cursor2.execute("SELECT urls.id_c FROM public.urls WHERE (urls.id_url='%d')" %(id))
        c = cursor2.fetchone()[0]
        data[c-1].append(text[1])                                   # Составить список для каждой категории.
        text = cursor.fetchone()
    cursor2.close()
    data_df = list()
    for i in range(len(data)):
        data_df.append([categories[i], " ".join(data[i])])
    all_text = pd.DataFrame(data_df, columns=['category', 'text'])
    vector = TfidfVectorizer()                                      # Вычислить TF-IDF-признаки для всех текстов.
    data = vector.fit_transform(all_text['text'])
    feature_mapping = vector.get_feature_names()                    # Список всех слов.
    tfidf = pd.DataFrame(data.todense(),
                      columns=feature_mapping,
                      index=all_text['category'])                   # Матрица TF-IDF
    get_dictionary(tfidf)


def get_dictionary(tfidf):
    """Составить словарь для каждой категории.

    Параметр:
    tfidf - pd.DataFrame
        Матрица со значениями TF-IDF. Индексы - названия категорий,
                                      колонки - слова.
    """
    for index, row in tfidf.iterrows():
        vex = list()
        for c in tfidf.columns:
            vex.append([index, c, row[c]])
        vex.sort(key=lambda i: i[2], reverse=1)                     # Сортировать по убыванию веса.
        df = pd.DataFrame(vex, columns=['cat', 'word', 'tif'])
        df = df[df['tif'] != 0]                                     # Удалить слова с нулевым весом.
        for index, row in df.iterrows():
            cursor.execute("INSERT INTO public.dictionary (category, word, tfidf) "
                           "VALUES ('%s','%s', '%f')" % (row['cat'], row['word'], row['tif']))
            conn.commit()


if __name__ == '__main__':
    pswrd = input('password:')
    conn = psycopg2.connect(dbname=DATABASE, user=USER, password=pswrd)  # подключение к БД
    cursor = conn.cursor()
    
    open_directory('webdata/')                                  # Записать в БД адреса веб-страниц.
    html_tags = pd.read_csv('html_tags.csv', header=None)       # Загрузить теги для страниц.
    get_tags(html_tags)                                         # Веб-скрапинг по тегам.
    get_matrix_tfidf()                                          # Составить матрицу tf-idf.

    cursor.close()
    conn.close()