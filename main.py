import os

import httpx
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient

from datetime import datetime
import pytz

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
load_dotenv()

SENDER_EMAIL_ADDRESS = os.getenv("SENDER_EMAIL_ADDRESS")
RECEIVER_EMAIL_ADDRESS = os.getenv("RECEIVER_EMAIL_ADDRESS")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
EMAIL_APP_PASS = os.getenv("EMAIL_APP_PASS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE = os.getenv("DATABASE")
COLLECTION = os.getenv("NEW_COLLECTION")
MODEL_NAME = os.getenv("NEW_MODEL")

tz = pytz.timezone(os.getenv("TIME_ZONE"))

import markdown
def send_email(subject:str, body:str):
    load_dotenv()
    try:
        html_body = markdown.markdown(body)
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL_ADDRESS
        msg['To'] = RECEIVER_EMAIL_ADDRESS
        msg['Subject'] = subject

        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL_ADDRESS, EMAIL_APP_PASS)
            server.sendmail(SENDER_EMAIL_ADDRESS, RECEIVER_EMAIL_ADDRESS, msg.as_string())
        return "Email sent successfully."

    except Exception as e:
        return f"An error occurred: {e}"

def format_chat_history(history_chat):
    chat_content = []
    print("transforming it into required format.")
    for chat in history_chat:
        try:
            user_text = chat["user"]
            chat_content.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))
        except KeyError:
            try:
                model_text = chat["model"]
                chat_content.append(types.Content(role="model", parts=[types.Part.from_text(text=model_text)]))
            except KeyError:
                try:
                    function_call = chat["function"]
                    chat_content.append(types.Content(role="model", parts=[
                        types.Part.from_function_call(name=function_call["name"], args=function_call["args"])]))
                except KeyError:
                    function_response = chat["function_response"]
                    chat_content.append(types.Content(role="function", parts=[
                        types.Part.from_function_response(name=function_response["name"],
                                                          response=function_response["response"])]))
    print("data transformation complete.")
    return chat_content

def get_chat_history():
    print("connecting to database.")
    client = MongoClient(MONGODB_URI)
    collection = client.get_database(DATABASE).get_collection(COLLECTION)
    print("fetching required data.")
    chat_history = collection.find().sort({"time": 1})
    chat_content = format_chat_history(history_chat=chat_history)
    client.close()
    return chat_content


def generate(contents):
    client = genai.Client(
        api_key=GEMINI_API_KEY,
    )
    model = MODEL_NAME
    tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="send_email",
                    description="sends email to end user",
                    parameters=genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "subject": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "body": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
                ),
            ])
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=0.9,
        tools=tools,
        response_mime_type="text/plain",
        system_instruction=[
            types.Part.from_text(text=os.getenv("NEW_PROMPT")),
        ],
        thinking_config=types.ThinkingConfig(thinking_budget=1024)
    )

    return client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

def set_chat_history(message: dict):
    client = MongoClient(MONGODB_URI)
    collection = client.get_database(DATABASE).get_collection(COLLECTION)
    collection.insert_one(message)
    client.close()


if __name__ == "__main__":
    chat_messages = get_chat_history()
    print("acquired the data.")
    try:
        # inputText =  input(":")
        inputText =  "SEND_MORNING" if int(datetime.now(tz).strftime("%H")) <= 12 else "SEND_EVENING"
        set_chat_history({"user": inputText, "time": datetime.now(tz)})
        chat_messages.append(types.Content(role="user", parts=[types.Part.from_text(text=inputText)]))
        response = generate(chat_messages)
        if response.function_calls is None:
            print(f"Model Response: {response.text}")
            chat_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=response.text)]))
            set_chat_history({"model": response.text, "time": datetime.now(tz)})
        while response.function_calls is not None:
            function_response = {"result": send_email(**response.function_calls[0].args)}
            function_name = response.function_calls[0].name
            print("model called the function.")
            chat_messages.append(types.Content(role="model", parts=[
                types.Part.from_function_call(name=function_name,
                                              args=response.function_calls[0].args)]))
            set_chat_history(
                    {"function": {"name": response.function_calls[0].name, "args": response.function_calls[0].args},
                     "time": datetime.now(tz)})
            print("function calling ended.")
            chat_messages.append(types.Content(role="function", parts=[
                types.Part.from_function_response(name=response.function_calls[0].name,
                                                  response=function_response)]))
            set_chat_history(
                {"function_response": {"name": response.function_calls[0].name, "response": function_response},
                 "time": datetime.now(tz)})
            print("model received function response.")
            response = generate(chat_messages)
            if response.function_calls is None:
                print(f"Response After Function Call: {response.text}")
                chat_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=response.text)]))
                set_chat_history({"model": response.text, "time": datetime.now(tz)})

            print("responded to function")
    except httpx.ConnectError:
        print("failed to connect the internet.")
