# -*- coding: utf-8 -*-

import json
import time
import psycopg2
import requests
import schedule
import trello
import urllib3
import vk_api.vk_api
import socket

from contextlib import closing

from psycopg2.extras import RealDictCursor

from threading import Thread

from vk_api.bot_longpoll import VkBotLongPoll
from vk_api.bot_longpoll import VkBotEventType
from vk_api.utils import get_random_id

from vk_keyboards import kb_start

from config import *


def execute_sql(sql_query, connection_params):
    with closing(psycopg2.connect(cursor_factory=RealDictCursor,
                                  dbname=connection_params["dbname"],
                                  user=connection_params["user"],
                                  password=connection_params["password"],
                                  host=connection_params["host"],
                                  port=connection_params["port"],
                                  )) as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(sql_query)
            try:
                records = cursor.fetchall()
                result = []
                for record in records:
                    result.append(dict(record))
                return result
            except psycopg2.ProgrammingError:
                pass


def fetch_tboards_by_name(tclient, tboard_name):
    tboards = []
    tboards_all = tclient.list_boards(board_filter="open")
    for tboard in tboards_all:
        if tboard.name == tboard_name:
            tboards.append(tboard)
    return tboards


def fetch_tlists_by_name(tboard, tlist_name):
    tlists = []
    tlists_all = tboard.list_lists(list_filter="open")
    for tlist in tlists_all:
        if tlist.name == tlist_name:
            tlists.append(tlist)
    return tlists


def fetch_checklists_by_tlist(tlist):
    checklists = {}
    tcards = tlist.list_cards(card_filter="open")
    for tcard in tcards:
        checklists[tcard.name] = {}
        tchecklists = tcard.fetch_checklists()
        for tchecklist in tchecklists:
            checklists[tcard.name][tchecklist.name] = {}
            ttasks = tchecklist.items
            for ttask in ttasks:
                checklists[tcard.name][tchecklist.name][ttask["name"]] = ttask["state"]
    return checklists


def make_checklists_pretty(checklists_dict):
    pretty_checklists = ""
    cards = checklists_dict.keys()
    for card in cards:
        pretty_checklists = pretty_checklists + card + "\n"
        checklists_names = checklists_dict[card].keys()
        for checklist_name in checklists_names:
            pretty_checklists = pretty_checklists + "____" + checklist_name + "\n"
            tasks = checklists_dict[card][checklist_name].keys()
            for task in tasks:
                pretty_checklists = pretty_checklists + "________" + task + " "
                if checklists_dict[card][checklist_name][task] == "complete":
                    pretty_checklists += "✔\n"
                else:
                    pretty_checklists += "❌\n"
        pretty_checklists += "\n"
    return pretty_checklists


def calculate_percent_done(checklists_dict):
    tasks_count_total = 0
    tasks_count_completed = 0
    cards = checklists_dict.keys()
    for card in cards:
        checklists_names = checklists_dict[card].keys()
        for checklist_name in checklists_names:
            tasks = checklists_dict[card][checklist_name].keys()
            for task in tasks:
                tasks_count_total += 1
                if checklists_dict[card][checklist_name][task] == "complete":
                    tasks_count_completed += 1
    percent_done = tasks_count_completed / tasks_count_total
    percent_done = round(percent_done * 100)
    return percent_done


def send_message(peer_id, message=None, keyboard=None, attachment=None):
    if len(message) > 4096:
        text = [message[i:i + 4096] for i in range(0, len(message), 4096)]
        last_words = text[-1]
        text = text[:-1]
        for t in text:
            vk_api.messages.send(peer_id=peer_id,
                                 message=t,
                                 random_id=get_random_id()
                                 )
            time.sleep(0.5)
        vk_api.messages.send(peer_id=peer_id,
                             message=last_words,
                             keyboard=keyboard,
                             attachment=attachment,
                             random_id=get_random_id()
                             )
    else:
        vk_api.messages.send(peer_id=peer_id,
                             message=message,
                             keyboard=keyboard,
                             attachment=attachment,
                             random_id=get_random_id()
                             )


def get_button(label, color):
    return {
        "action": {
            "type": "text",
            "label": label
        },
        "color": color
    }


def prepare_keyboard(kb):
    kb = json.dumps(kb, ensure_ascii=False).encode('utf-8')
    kb = str(kb.decode('utf-8'))
    return kb


def labels_to_keyboard(labels):
    buttons = []
    for label in labels:
        button = [get_button(label=label, color="default")]
        buttons.append(button)
    kb = {
        "one_time": True,
        "buttons": buttons
    }
    kb = prepare_keyboard(kb)
    return kb


def check_user(vk_id):
    res = execute_sql("SELECT * FROM users WHERE vk_id={}".format(vk_id), POSTGRES_CONNECTION_PARAMS)
    if len(res) != 0:
        return True
    else:
        return False


def step_0(request):
    if request["message"] == "Начать":
        execute_sql("UPDATE users SET step = 1 WHERE vk_id = {};".format(request["vk_id"]), POSTGRES_CONNECTION_PARAMS)

        send_message(request["vk_id"],
                     message="Чтобы получить доступ к Trello, мне нужны ключ и токен. Здесь подробно описывается, как"
                             " их получить",
                     attachment="wall-195722017_2")
    else:
        send_message(
            request["vk_id"],
            message="Ты сможешь нажать на кнопку \"Начать\"! Я верю в тебя!",
            keyboard=kb_start)


def step_1(request):
    try:
        trello_api_key, trello_api_token = request["message"].split(" ")
        trello_client = trello.TrelloClient(api_key=trello_api_key, token=trello_api_token)
        trello_boards = trello_client.list_boards(board_filter="open")
        last_board = trello_boards[-1]
        trello_boards = trello_boards[:-1]

        execute_sql("UPDATE users SET trello_api_key='{}', trello_api_token='{}', step=2 WHERE vk_id= {}".format(
            trello_api_key, trello_api_token, request["vk_id"]
        ), POSTGRES_CONNECTION_PARAMS)

        message = "Ура, все получилось!\n\n" \
                  "Теперь отправь название доски, с которой нужно брать задачи.\n\n" \
                  "Твои доски: "
        for board in trello_boards:
            message = message + board.name + ", "
        message += last_board.name

        keyboard = None
        if len(trello_boards) < 9:
            trello_boards = [board.name for board in trello_boards]
            trello_boards.append(last_board.name)
            keyboard = labels_to_keyboard(trello_boards)

        send_message(request["vk_id"],
                     message=message,
                     keyboard=keyboard)
    except (trello.exceptions.Unauthorized, ValueError, IndexError):
        send_message(request["vk_id"],
                     message="Хмм, что-то не так. Перечитай мануал и попробуй снова")


def step_2(request):
    try:
        trello_client = trello.TrelloClient(api_key=request["trello_api_key"], token=request["trello_api_token"])
        tboard_daily = fetch_tboards_by_name(trello_client, request["message"])[0]
        tlists = tboard_daily.list_lists(list_filter="open")
        last_tlist = tlists[-1]
        tlists = tlists[:-1]

        execute_sql("UPDATE users SET trello_board='{}', step=3 WHERE vk_id={}".format(request["message"],
                                                                                       request["vk_id"]),
                    POSTGRES_CONNECTION_PARAMS)

        message = "Отлично. Теперь выбери список, в котором ты указываешь задачи на день.\n\n" \
                  "Вот они, слева направо: "
        for tlist in tlists:
            message = message + tlist.name + ", "
        message += last_tlist.name

        keyboard = None
        if len(tlists) < 9:
            tlists = [tlist.name for tlist in tlists]
            tlists.append(last_tlist.name)
            keyboard = labels_to_keyboard(tlists)

        send_message(request["vk_id"],
                     message=message,
                     keyboard=keyboard)
    except IndexError:
        send_message(request["vk_id"],
                     message="Выбери доску, с которой нужно брать задачи")


def step_3(request):
    try:
        trello_client = trello.TrelloClient(api_key=request["trello_api_key"], token=request["trello_api_token"])
        tboard_daily = fetch_tboards_by_name(trello_client, request["trello_board"])[0]
        tlist_daily = fetch_tlists_by_name(tboard_daily, request["message"])[0]
        checklists_daily_dict = fetch_checklists_by_tlist(tlist_daily)

        execute_sql("UPDATE users SET trello_list='{}', step=4 WHERE vk_id={}".format(request["message"],
                                                                                      request["vk_id"]),
                    POSTGRES_CONNECTION_PARAMS)

        pretty_checklists = make_checklists_pretty(checklists_daily_dict)
        percent_done_today = calculate_percent_done(checklists_daily_dict)
        message = "Твои задачи на сегодня\n\n" + pretty_checklists + "Выполненных задач за сегодня: " + \
                  str(percent_done_today) + "%"

        keyboard = labels_to_keyboard(["Проверить задачи"])
        send_message(request["vk_id"],
                     message=message,
                     keyboard=keyboard)
    except IndexError:
        send_message(request["vk_id"],
                     message="Но такого списка нет...")


def step_4(request):
    trello_client = trello.TrelloClient(api_key=request["trello_api_key"], token=request["trello_api_token"])
    tboard_daily = fetch_tboards_by_name(trello_client, request["trello_board"])[0]
    tlist_daily = fetch_tlists_by_name(tboard_daily, request["trello_list"])[0]
    checklists_daily_dict = fetch_checklists_by_tlist(tlist_daily)
    pretty_checklists = make_checklists_pretty(checklists_daily_dict)

    percent_done_today = calculate_percent_done(checklists_daily_dict)

    message = "Твои задачи на сегодня\n\n" + pretty_checklists + "Выполненных задач за сегодня: " + \
              str(percent_done_today) + "%\n" + "В день выполняется в среднем: " + \
              str(request["total_percent"]) + "%"
    keyboard = labels_to_keyboard(["Проверить задачи"])
    send_message(request["vk_id"],
                 message=message,
                 keyboard=keyboard)


def daily_update():
    users = execute_sql("SELECT * FROM users", POSTGRES_CONNECTION_PARAMS)
    for user in users:
        try:
            trello_client = trello.TrelloClient(api_key=user["trello_api_key"], token=user["trello_api_token"])
            tboard_daily = fetch_tboards_by_name(trello_client, user["trello_board"])[0]
            tlist_daily = fetch_tlists_by_name(tboard_daily, user["trello_list"])[0]
            checklists_daily_dict = fetch_checklists_by_tlist(tlist_daily)

            percent_done_today = calculate_percent_done(checklists_daily_dict)
            percent_done_total = (user["days"] * user["total_percent"] + percent_done_today) / (user["days"] + 1)

            message = "Выполненных задач за сегодня: " + str(percent_done_today) + "%\n" + \
                      "В день выполняется в среднем: " + str(percent_done_total) + "%"
            send_message(user["vk_id"],
                         message=message)

            execute_sql("UPDATE users SET days={}, total_percent={} WHERE vk_id={}".format(user["days"] + 1,
                                                                                           percent_done_total,
                                                                                           user["vk_id"]),
                        POSTGRES_CONNECTION_PARAMS)
        except (trello.exceptions.Unauthorized, ValueError, IndexError)
            pass


def shedule_update_loop():
    schedule.every().day.at("23:59").do(daily_update)
    while True:
        schedule.run_pending()
        time.sleep(1)


steps = {
    0: step_0,
    1: step_1,
    2: step_2,
    3: step_3,
    4: step_4
}

vk_session = vk_api.VkApi(token=VK_API_TOKEN)
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)
vk_api = vk_session.get_api()


def trello_vk_bot():
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_NEW:
                    user_id = event.raw["object"]["message"]["from_id"]
                    if not check_user(user_id):
                        execute_sql("INSERT into users (vk_id, step, days, total_percent) "
                                    "VALUES ({}, 0, 0, 0.0);".format(user_id),
                                    POSTGRES_CONNECTION_PARAMS)
                        user_request = {
                            "vk_id": user_id,
                            "message": event.raw["object"]["message"]["text"]
                        }
                        step_0(user_request)
                    else:
                        user_request = execute_sql("SELECT * FROM users WHERE vk_id={}".format(user_id),
                                                   POSTGRES_CONNECTION_PARAMS)[0]
                        user_request["message"] = event.raw["object"]["message"]["text"]
                        step_func = steps[user_request["step"]]
                        step_func(user_request)
        except (requests.exceptions.ReadTimeout, urllib3.exceptions.ReadTimeoutError, socket.timeout):
            pass


def main():
    thread1 = Thread(target=trello_vk_bot)
    thread2 = Thread(target=shedule_update_loop)
    thread1.start()
    thread2.start()
    print("let it burn")
    thread1.join()
    thread2.join()


if __name__ == '__main__':
    main()
