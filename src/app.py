from flask import (
    Flask,
    jsonify,
    request,
    session,
    make_response,
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from db import (
    close_db,
    get_db,
)


app = Flask(__name__)
app.teardown_appcontext(close_db)
app.secret_key = b'123ff'


@app.route('/auth/login', methods=['POST'])
def login():
    request_json = request.json
    email = request_json.get('email')
    password = request_json.get('password')
    cur = get_db().cursor()
    query_get_id = f"""
        SELECT id
        FROM account
        WHERE email = "{email}";
    """
    query_get_password_hash = f"""
        SELECT password
        FROM account
        WHERE email = "{email}";
    """
    cur.execute(query_get_id)
    user_id = cur.fetchone()
    cur.execute(query_get_password_hash)
    password_hash = cur.fetchone()
    is_password = check_password_hash(password_hash['password'], password)
    # Ставит сессии None если вход выполняется впервые
    if user_id is not None and not session.get('user_id', None) and is_password:
        session['user_id'] = user_id[0]
    elif user_id is not None and session.get('user_id'):
        return 'You are logged already!', 200
    else:
        return 'Login forbidden!', 404
    return 'You are logged!', 200


@app.route('/auth/logout', methods=['GET'])
def logout():
    session.clear()
    return 'Logout!', 200


@app.route('/users', methods=['POST'])
def user_register():
    # Тело запроса (Body - row - JSON)
    # {
    #     "email": "12121212",
    #     "password": "123",
    #     "first_name": "123",
    #     "last_name": "123",
    #     "is_seller": true,
    #     "phone": "123",
    #     "zip_code": 10100,
    #     "city_id": 100,
    #     "street": "123",
    #     "home": "123"
    # }
    request_json = request.json
    email = request_json.get('email')
    password = request_json.get('password')
    password_hash = generate_password_hash(password)
    first_name = request_json.get('first_name')
    last_name = request_json.get('last_name')
    is_seller = request_json.get('is_seller')
    # Запрос на добавление аккаунта
    query_account = f"""
        INSERT OR IGNORE INTO account (first_name, last_name, email, password)
        VALUES ("{first_name}", "{last_name}", "{email}", "{password_hash}");
    """

    # Есть ли аккаунт в базе - запись в account или 400
    cur = get_db().cursor()
    query_get_id = f"""
            SELECT id
            FROM account
            WHERE email = "{email}";
        """
    cur.execute(query_get_id)
    account_id = cur.fetchone()
    if account_id is not None:
        return 'Email is in db!', 400
    else:
        cur.execute(query_account)
        get_db().commit()
        query_get_id = f"""
                    SELECT id
                    FROM account
                    WHERE email = "{email}";
                """
        cur.execute(query_get_id)
        account_id = cur.fetchone()

    if is_seller:
        phone = request_json.get('phone')
        zip_code = request_json.get('zip_code')
        city_id = request_json.get('city_id')
        street = request_json.get('street')
        home = request_json.get('home')
        # Запрос на добавление продавца
        query_seller = f"""
            INSERT INTO seller (street, home, phone, account_id, zip_code)
            VALUES ("{street}", "{home}", "{phone}", {account_id[0]}, {zip_code});
        """
        # Извлечение zip_code из zipCode
        query_get_zip_code = f"""
            SELECT zip_code 
            FROM zipcode
            WHERE zip_code = {zip_code};
        """
        cur.execute(query_get_zip_code)
        zip_code_sql = cur.fetchone()
        # Извлечение city_id из City
        query_get_city_id = f"""
            SELECT id
            FROM city
            WHERE id = {city_id};
        """
        cur.execute(query_get_city_id)
        city_id_sql = cur.fetchone()

        if zip_code_sql is not None and city_id_sql is not None:
            cur.execute(query_seller)
            get_db().commit()
            response = make_response({
                'id': account_id[0],
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_seller": is_seller,
                "phone": phone,
                "zip_code": zip_code,
                "city_id": city_id,
                "street": street,
                "home": home
                }, 200)
            return response
        elif city_id_sql is None:
            response = make_response(f'Change city_id != {city_id}', 400)
            return response
        elif zip_code_sql is None:
            query_zipcode = f"""
                INSERT INTO zipcode (zip_code, city_id)
                VALUES ({zip_code}, {city_id});
            """
            cur.execute(query_zipcode)
            get_db().commit()
            cur.execute(query_seller)
            get_db().commit()
            response = make_response({
                'id': account_id[0],
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_seller": is_seller,
                "phone": phone,
                "zip_code": zip_code,
                "city_id": city_id,
                "street": street,
                "home": home
            }, 200)
            return response
    else:
        response = make_response({
            'id': account_id[0],
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_seller": is_seller
        })
        return response


@app.route('/users/<int:id>', methods=['GET', 'PATCH'])
def user_get(id):
    # Тело запроса (Body - row - JSON)
    # {
    #     "first_name": str?,
    #     "last_name": str?,
    #     "is_seller": bool?,
    #     "phone": str?,
    #     "zip_code": int?,
    #     "city_id": int?,
    #     "street": str?,
    #     "home": str?
    # }
    # Получение из account
    cur = get_db().cursor()
    query_get_account = f"""
                SELECT *
                FROM account
                WHERE id = {id}
            """
    cur.execute(query_get_account)
    account = cur.fetchone()
    # Получение пользователя, продавец / клиент - разные ответы
    if auth_required() and request.method == 'GET':
        # Получение из seller
        query_get_seller = f"""
                    SELECT * 
                    FROM seller
                    WHERE account_id = {id}
                """
        cur.execute(query_get_seller)
        seller = cur.fetchone()

        response = make_response({"id": account['id'],
                                  "email": account['email'],
                                  "first_name": account['first_name'],
                                  "last_name": account['last_name'],
                                  "is_seller": False
                                  }, 200)
        if seller:
            # Получение из zipcode
            query_get_city_id = f"""
                        SELECT city_id
                        FROM zipcode
                        WHERE zip_code = {seller['zip_code']};
                    """
            cur.execute(query_get_city_id)
            zip_code = cur.fetchone()
            response = make_response({"id": account['id'],
                                      "email": account['email'],
                                      "first_name": account['first_name'],
                                      "last_name": account['last_name'],
                                      "is_seller": True,
                                      "phone": seller['phone'],
                                      "zip_code": seller['zip_code'],
                                      "city_id": zip_code['city_id'],
                                      "street": seller['street'],
                                      "home": seller['home']
                                  }, 200)
        return response
    # Редактирование пользователя, продавец / клиент - разные ответы
    if auth_required() == id and request.method == 'PATCH':
        cur = get_db().cursor()
        request_json = request.json
        first_name = request_json.get('first_name')
        last_name = request_json.get('last_name')
        # Извлечь из словаря is_seller - обновить account
        is_seller = request_json.get('is_seller')
        query_patch_account = f"""
            UPDATE account
            SET first_name = "{first_name}",
                last_name = "{last_name}"
            WHERE id = {id};
        """
        cur.execute(query_patch_account)
        get_db().commit()
        if not is_seller:
            query_patch_seller = f"""
                DELETE FROM seller
                WHERE account_id = {id};
            """
            cur.execute(query_patch_seller)
            get_db().commit()
            response = make_response({"id": id,
                                      "email": account['email'],
                                      "first_name": first_name,
                                      "last_name": last_name,
                                      "is_seller": False
                                      }, 200)
            return response

        if is_seller:
            phone = request_json.get('phone')
            zip_code = request_json.get('zip_code')
            city_id = request_json.get('city_id')
            street = request_json.get('street')
            home = request_json.get('home')

            query_patch_seller_zipcode = f"""
                INSERT OR REPLACE INTO seller (phone, zip_code, street, home, account_id)
                VALUES ("{phone}", {zip_code}, "{street}", "{home}", {id});

                UPDATE zipcode
                SET city_id = {city_id}
                WHERE zip_code = {zip_code};
            """
            cur.executescript(query_patch_seller_zipcode)
            get_db().commit()
            response = make_response({"id": id,
                                      "email": account['email'],
                                      "first_name": first_name,
                                      "last_name": last_name,
                                      "is_seller": True,
                                      "phone": phone,
                                      "zip_code": zip_code,
                                      "city_id": city_id,
                                      "street": street,
                                      "home": home
                                      }, 200)
            return response

    return 'Bad request!', 400


@app.route('/ads', methods=['GET'])
def ads():
    # Тело запроса (Body - row - TEXT)
    # Query string:
    # seller_id: int?
    # tags: str?
    # make: str?
    # model: str?
    request_data = request.data.decode("utf-8")
    request_list = request_data.split()
    data = {}
    try:
        request_list.remove('Query')
        request_list.remove('string:')
    except ValueError:
        pass
    for elem in request_list:
        if elem == 'seller_id:':
            seller_id_index = request_list.index(elem) + 1
            data['seller_id'] = request_list[seller_id_index]
            request_list.remove(elem)
            request_list.remove(request_list[seller_id_index - 1])
        if elem == 'make:':
            make_index = request_list.index(elem) + 1
            data['make'] = request_list[make_index]
            request_list.remove(elem)
            request_list.remove(request_list[make_index - 1])
    for elem in request_list:
        if elem == 'model:':
            model_index = request_list.index(elem) + 1
            data['model'] = request_list[model_index]
            request_list.remove(elem)
            request_list.remove(request_list[model_index - 1])
    for elem in request_list:
        if elem == 'tags:':
            request_list.remove(elem)
    if request_list:
        row_tags = ''.join(elem for elem in request_list)
        list_tags = row_tags.split(',')
        data['tags'] = list_tags

    get_ads = f"""
        SELECT DISTINCT ad.id, 
            ad.seller_id, 
            ad.title, 
            ad.date, 
            t.name, 
            c.make, 
            c.model,
            col.id,
            col.name,
            col.hex,
            c.mileage,
            c.num_owners,
            c.reg_number,
            i.title,
            i.url
        FROM ad 
            JOIN adtag ON ad.id = adtag.ad_id
            JOIN tag AS t ON adtag.tag_id = t.id
            JOIN car AS c ON ad.car_id = c.id
            JOIN carcolor ON c.id = carcolor.car_id
            JOIN color AS col ON carcolor.color_id = col.id
            JOIN image AS i ON c.id = i.car_id """

    if data.get('seller_id', None) and get_ads.find('WHERE') != -1:
        get_param_1 = f"""
            AND ad.seller_id = {data.get('seller_id')} """
        get_ads = get_ads + get_param_1
    elif data.get('seller_id', None) and get_ads.find('WHERE') == -1:
        get_param_1 = f"""
            WHERE ad.seller_id = {data.get('seller_id')} """
        get_ads = get_ads + get_param_1

    if data.get('make', None) and get_ads.find('WHERE') != -1:
        get_param_2 = f"""
            AND c.make = "{data.get('make', None)}" """
        get_ads = get_ads + get_param_2
    elif data.get('make', None) and get_ads.find('WHERE') == -1:
        get_param_2 = f"""
            WHERE c.make = "{data.get('make', None)}" """
        get_ads = get_ads + get_param_2

    if data.get('model', None) and get_ads.find('WHERE') != -1:
        get_param_3 = f"""
            AND c.model = "{data.get('model', None)}" """
        get_ads = get_ads + get_param_3
    elif data.get('model', None) and get_ads.find('WHERE') == -1:
        get_param_3 = f"""
            WHERE c.model = "{data.get('model', None)}" """
        get_ads = get_ads + get_param_3

    tags_list = data.get('tags', None)
    if tags_list and get_ads.find('WHERE') != -1:
        for tag in tags_list:
            get_tags = f"""
                AND t.name = "{tag}" """
            get_ads = get_ads + get_tags

    if tags_list and get_ads.find('WHERE') == -1:
        get_tags = f"""
            WHERE t.name = "{tags_list[0]}" """
        get_ads = get_ads + get_tags
        for tag in tags_list[1:]:
            get_tags = f"""
                AND t.name = "{tag}" """
            get_ads = get_ads + get_tags

    cur = get_db().cursor()
    cur.execute(get_ads)
    result_ads = []
    for line in cur.fetchall():
        result_ads.append(dict(line))

    response = make_response(f"{result_ads}")
    return response


@app.route('/users/<int:id>/ads')
def user_ads(id):
    # Тело запроса (Body - row - TEXT)
    # Query string:
    # tags: str?
    # make: str?
    # model: str?
    request_data = request.data.decode("utf-8")
    request_list = request_data.split()
    data = {}
    try:
        request_list.remove('Query')
        request_list.remove('string:')
    except ValueError:
        pass
    for elem in request_list:
        if elem == 'make:':
            make_index = request_list.index(elem) + 1
            data['make'] = request_list[make_index]
            request_list.remove(elem)
            request_list.remove(request_list[make_index - 1])
    for elem in request_list:
        if elem == 'model:':
            model_index = request_list.index(elem) + 1
            data['model'] = request_list[model_index]
            request_list.remove(elem)
            request_list.remove(request_list[model_index - 1])
    for elem in request_list:
        if elem == 'tags:':
            request_list.remove(elem)
    if request_list:
        row_tags = ''.join(elem for elem in request_list)
        list_tags = row_tags.split(',')
        data['tags'] = list_tags

    get_ads = f"""
        SELECT DISTINCT ad.id, 
            ad.seller_id, 
            ad.title, 
            ad.date, 
            t.name, 
            c.make, 
            c.model,
            col.id,
            col.name,
            col.hex,
            c.mileage,
            c.num_owners,
            c.reg_number,
            i.title,
            i.url
        FROM ad 
            JOIN adtag ON ad.id = adtag.ad_id
            JOIN tag AS t ON adtag.tag_id = t.id
            JOIN car AS c ON ad.car_id = c.id
            JOIN carcolor ON c.id = carcolor.car_id
            JOIN color AS col ON carcolor.color_id = col.id
            JOIN image AS i ON c.id = i.car_id
            WHERE ad.seller_id = {id} """

    if data.get('make', None):
        get_param_1 = f"""
            AND c.make = "{data.get('make', None)}" """
        get_ads = get_ads + get_param_1

    if data.get('model', None):
        get_param_2 = f"""
            AND c.model = "{data.get('model', None)}" """
        get_ads = get_ads + get_param_2

    tags_list = data.get('tags', None)
    if tags_list:
        for tag in tags_list:
            get_tags = f"""
                AND t.name = "{tag}" """
            get_ads = get_ads + get_tags

    cur = get_db().cursor()
    cur.execute(get_ads)
    result_ads = []
    for line in cur.fetchall():
        result_ads.append(dict(line))

    response = make_response(f"{result_ads}")
    return response


@app.route('/ads/<int:id>', methods=['GET', 'DELETE'])
def get_ad(id):
    cur = get_db().cursor()
    if request.method == 'GET':
        get_ad = f"""
                SELECT DISTINCT ad.id, 
                    ad.seller_id, 
                    ad.title, 
                    ad.date, 
                    t.name, 
                    c.make, 
                    c.model,
                    col.id,
                    col.name,
                    col.hex,
                    c.mileage,
                    c.num_owners,
                    c.reg_number,
                    i.title,
                    i.url
                FROM ad 
                    JOIN adtag ON ad.id = adtag.ad_id
                    JOIN tag AS t ON adtag.tag_id = t.id
                    JOIN car AS c ON ad.car_id = c.id
                    JOIN carcolor ON c.id = carcolor.car_id
                    JOIN color AS col ON carcolor.color_id = col.id
                    JOIN image AS i ON c.id = i.car_id
                    WHERE ad.id = {id}
                    GROUP BY t.name"""
        cur.execute(get_ad)
        result_ad = []
        for line in cur.fetchall():
            result_ad.append(dict(line))

        response = make_response(f"{result_ad}")
        return response

    if request.method == 'DELETE':
        delete_ad = f"""
                DELETE FROM ad
                WHERE ad.id = {id};
            """
        cur.execute(delete_ad)
        get_db().commit()
        response = make_response(f'Delete ad {id}', 200)
        return response


@app.route('/cities', methods=['GET', 'POST'])
def create_city():
    # Тело запроса (Body - row - JSON) ['POST']
    # {
    #     "name": str
    # }
    if request.method == 'POST':
        request_json = request.json
        city_name = request_json.get('name')
        get_city = f"""
            SELECT id, name
            FROM city
            WHERE name = "{city_name}";
        """
        create_city = f"""
            INSERT OR IGNORE INTO city (name)
            VALUES ("{city_name}");
        """
        cur = get_db().cursor()
        cur.execute(create_city)
        get_db().commit()
        cur.execute(get_city)
        city_sql = cur.fetchone()
        response = {
                    'id': city_sql['id'],
                    'name': city_sql['name']
                    }
        return response, 200

    if request.method == 'GET':
        get_city = f"""
            SELECT id, name
            FROM city
        """
        cur = get_db().cursor()
        cur.execute(get_city)
        city_list = []
        for city in cur.fetchall():
            city_list.append(dict(city))
        response = make_response(f"{city_list}", 200)
        return response


@app.route('/colors', methods=['GET', 'POST'])
def get_colors():
    # Тело запроса (Body - row - JSON) ['POST']
    # {
    #     "name": str,
    #     "hex": str
    # }
    request_json = request.json
    color_name = request_json.get('name')
    hex = request_json.get('hex')
    user_id = session['user_id']
    get_seller_id = f"""
        SELECT s.id
        FROM seller AS s
            JOIN account AS a ON a.id = s.account_id
        WHERE a.id = {user_id}
    """
    cur = get_db().cursor()
    cur.execute(get_seller_id)
    seller_id = cur.fetchone()
    response = ('Bad request!', 400)
    get_colors = f"""
                SELECT *
                FROM color """
    if request.method == 'GET' and auth_required() and seller_id:
        cur.execute(get_colors)
        colors_dict = cur.fetchall()
        colors_list = []
        for color in colors_dict:
            colors_list.append(dict(color))

        response = make_response(f'{colors_list}', 200)
    if request.method == 'POST' and auth_required() and seller_id:
        get_colors_2 = f"""
                    WHERE color.name = "{color_name}";
                """
        get_colors = get_colors + get_colors_2
        cur.execute(get_colors)
        color_sql = cur.fetchone()
        if color_sql:
            response = make_response(f"{dict(color_sql)}", 200)
        else:
            create_color = f"""
                INSERT OR IGNORE INTO color (name, hex)
                VALUES ("{color_name}", "{hex}");
            """
            cur.execute(create_color)
            get_db().commit()
            cur.execute(get_colors)
            color_sql = cur.fetchone()
            response = make_response(f"{dict(color_sql)}", 200)
    return response


def auth_required():
    return session.get('user_id', None)


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


if __name__ =='__main__':
    app.run()