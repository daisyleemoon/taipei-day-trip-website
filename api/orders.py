from flask import *
import jwt
from models.order import *
from urllib.request import Request, urlopen
from os import environ, path
from dotenv import load_dotenv


basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))


orders = Blueprint("orders", __name__)


@orders.route("/api/orders", methods=["POST", "GET"])
def post_request_order():
    if not request.cookies.get("cookie"):
        error = {"error": True, "message": "未登入系統，拒絕存取"}
        return jsonify(error), 403
    if request.method == "POST":
        try:
            if not request.get_json():
                error = {"error": True, "message": "訂單建立失敗，輸入不正確或其他原因"}
                return jsonify(error), 400
            member_id = get_member_id(request)
            prime = get_prime(request)
            tour_order = get_tour_order(request, member_id)
            tour_order.insert()
            tappay_response = post_to_tappay(prime, tour_order)

            if tappay_response["status"] == 0:
                tour_order.payment_status = "paid"
                tour_order.update(tappay_response)
            else:
                tour_order.update(tappay_response)
            return jsonify(tour_order.order_number)
        except:
            error = {"error": True, "message": "伺服器內部錯誤"}
            return jsonify(error), 500
    if request.method == "GET":
        member_id = get_member_id(request)
        return jsonify(Order.search_by_member_id(member_id))


@orders.route("/api/orders/<orderNumber>", methods=["GET"])
def get_request_order(orderNumber):
    if not request.cookies.get("cookie"):
        error = {"error": True, "message": "未登入系統，拒絕存取"}
        return jsonify(error), 403
    if request.method == "GET":
        if not orderNumber:
            error = {"error": True, "message": "輸入不正確或其他原因"}
            return jsonify(error), 400
        else:
            response = Order.search_by_order_number(orderNumber)
            if response is None:
                return jsonify(response)
            else:
                return jsonify(parse_reponse_data(response))


def get_member_id(request):
    cookie = request.cookies.get("cookie")
    decode_jwt = jwt.decode(cookie, current_app.config["SECRET_KEY"], algorithms="HS256")
    return decode_jwt["data"]["id"]


def get_prime(request):
    return request.get_json()["prime"]


def get_tour_order(request, member_id):
    tour_order = Order(
        member_id,
        request.get_json()["order"]["trip"]["attraction"]["id"],
        request.get_json()["order"]["trip"]["date"],
        request.get_json()["order"]["trip"]["time"],
        request.get_json()["order"]["price"],
        request.get_json()["order"]["contact"]["name"],
        request.get_json()["order"]["contact"]["email"],
        request.get_json()["order"]["contact"]["phone"],
    )

    return tour_order


def post_to_tappay(prime, tour_order):
    url = "https://sandbox.tappaysdk.com/tpc/payment/pay-by-prime"
    header_data = {
        "x-api-key": environ.get("PARTNER_KEY"),
        "Content-Type": "application/json",
    }
    body_data = {
        "prime": prime,
        "partner_key": environ.get("PARTNER_KEY"),
        "merchant_id": environ.get("MERCHANT_ID"),
        "details": "台北一日遊",
        "amount": tour_order.booking_price,
        "cardholder": {
            "name": tour_order.contact_name,
            "email": tour_order.contact_email,
            "phone_number": tour_order.contact_phone,
        },
        "remember": True,
    }
    req = Request(url, json.dumps(body_data).encode(), headers=header_data)
    url_open = urlopen(req)
    json_data = url_open.read().decode("utf-8")
    response = json.loads(json_data)
    return response


def parse_reponse_data(response):
    data = {
        "data": {
            "number": response[0],
            "price": response[4],
            "trip": {
                "attraction": {
                    "id": response[1],
                    "name": response[9],
                    "address": response[10],
                    "image": response[11].split(" | ")[0],
                },
                "date": response[2],
                "time": response[3],
            },
            "contact": {"name": response[5], "email": response[6], "phone": response[7]},
            "status": response[8],
        }
    }
    return data
