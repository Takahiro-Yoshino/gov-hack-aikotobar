# -*- coding: utf-8 -*-
import sys
sys.path.append('./vendor')

import os

from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    ButtonsTemplate, MessageTemplateAction, TemplateSendMessage, FollowEvent, ImageMessage, LocationMessage, LocationSendMessage,MessageEvent, TextMessage, TextSendMessage, StickerSendMessage
)

import redis
import cloudinary
import cloudinary.uploader
import uuid
import json
import urllib.parse

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))

url = urllib.parse.urlparse(os.environ["REDIS_URL"])
pool = redis.ConnectionPool(host=url.hostname,
                            port=url.port,
                            db=url.path[1:],
                            password=url.password,
                            decode_responses=True)
r = redis.StrictRedis(connection_pool=pool)

@app.route("/", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

def notifyBlankField(event):
    required = ['lat', 'lon', 'url', 'comment', 'review']
    done = r.hkeys(event.source.user_id)

    blank = list(set(required) - set(done))

    if len(blank) == 0:
        r.hset(event.source.user_id, 'userid', event.source.user_id)
        r.rename(event.source.user_id, 'lm_' + uuid.uuid4().hex)

        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text='added landmark. You can egister another landmark or view all data by sending \'show\'')
            ]
        )
    else:
        str = 'saved. required: ' + ', '.join(blank)
        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text=str)
            ]
        )

@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text="This BOT can store multiple landmark data that has location, image, comment and review. Send any of them."),
        ]
    )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):

    lat = event.message.latitude
    lon = event.message.longitude

    r.hmset(event.source.user_id, {'lat': lat, 'lon': lon})

    notifyBlankField(event)

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):

    message_content = line_bot_api.get_message_content(event.message.id)
    dirname = 'tmp'
    fileName = uuid.uuid4().hex
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open("tmp/{fileName}.jpg", 'wb') as img:
        img.write(message_content.content)

    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_NAME'),
        api_key = os.environ.get('CLOUDINARY_KEY'),
        api_secret = os.environ.get('CLOUDINARY_SECRET')
    )
    result = cloudinary.uploader.upload("tmp/{fileName}.jpg")
    r.hset(event.source.user_id, 'url', result['secure_url'])

    notifyBlankField(event)

#メッセージ入力後
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    
    event_mst={"event1":"arrive1","event2":"arrie2"}
    
    pos={"event1":("鶴ヶ城","〒965-0873福島県会津若松市追手町1-1",37.48772, 139.929794),"event2":("会津若松市役所","〒965-0035",37.48772,139.929794)}
    if event.message.text in pos:
        line_bot_api.reply_message(
            event.reply_token,
            [
                LocationSendMessage(
                    title     = pos[event.message.text][0],
                    address   = pos[event.message.text][1],
                    latitude  = pos[event.message.text][2],
                    longitude = pos[event.message.text][3]
                )
            ]
        )
    
    message1="クイズ：鶴ヶ城（会津城）の旧称はなんでしょう？"
    message2="合言葉は「あかべぇ」です"
    
    dist={"arrive1":("桜鍋 吉し多","〒965-0035福島県会津若松市東栄町5-14",37.494102,139.929993,message1,),"arrive2":("植木屋商店","〒965-0035福島県会津若松市馬場町1-35",37.497540,139.931335,message2)}
    eventtext=event.message.text
    if event.message.text in dist:
        r.decr(event_mst[event.message.text], 1)
        num=r.get(event_mst[event.message.text]).decode('utf-8')
        line_bot_api.reply_message(
            event.reply_token,
            [
                LocationSendMessage(
                    title     = dist[event.message.text][0],
                    address   = dist[event.message.text][1],
                    latitude  = dist[event.message.text][2],
                    longitude = dist[event.message.text][3]
                ),
                TextSendMessage(text=dist[eventtext][4])
            ]
        )
        

if __name__ == "__main__":
    app.debug = True;
    app.run()
