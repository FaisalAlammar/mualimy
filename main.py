from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate

import whisper
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiofiles
from uuid import uuid4
from typing import Dict, List
import requests
import time
from fastapi import APIRouter


# إعدادات Azure TTS
AZURE_API_KEY = "FsKgVmQOzmTmmaF4iYFt6sk0AhgKeqNdn5Ms4oFQNDpqxzGZSD3CJQQJ99BEACF24PCXJ3w3AAAYACOGIQN0"
AZURE_REGION = "uaenorth"
AZURE_ENDPOINT = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"

def azure_text_to_speech(text, output_path):
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_API_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3"
    }

    body = f"""
    <speak version='1.0' xml:lang='ar-SA'>
        <voice name='ar-SA-HamedNeural'>{text}</voice>
    </speak>
    """

    response = requests.post(AZURE_ENDPOINT, headers=headers, data=body.encode('utf-8'))

    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print("✅ تم توليد الرد الصوتي باللهجة السعودية.")
    else:
        print(f"❌ خطأ في تحويل النص إلى صوت: {response.status_code}")
        print(response.text)

app = FastAPI()

llm = Ollama(
    model="command-r7b-arabic",
    temperature=0.3,
    num_ctx=2048,
    num_thread=4
)

# Use Ollama as the subject router
def route_subject_with_llm(question: str) -> str:
    router_prompt = (
        "حدد بدقة موضوع السؤال التالي، فقط كلمة واحدة (فيزياء أو كيمياء أو أحياء)، ولا شيء غير ذلك.\n"
        f"السؤال: {question}\n"
        "الموضوع:"
    )
    response = llm(router_prompt)
    # Optionally: Clean up, make lowercase, etc.
    subject = response.strip().replace(" ", "").replace(":", "").lower()
    # Map to your subject system
    if "فيزياء" in subject:
        return "physics"
    if "كيمياء" in subject:
        return "chemistry"
    if "أحياء" in subject or "احياء" in subject:
        return "biology"
    return None

subject_db_map = {
    "physics":    ("db_physics",   "معلم الفيزياء"),
    "chemistry":  ("db_chemistry", "معلم الكيمياء"),
    "biology":    ("db_biology",   "معلم الأحياء"),
}


 

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/distiluse-base-multilingual-cased-v1"
)



conversation_memories: Dict[str, ConversationBufferMemory] = {}
chat_histories: Dict[str, List[Dict]] = {}
executor = ThreadPoolExecutor(max_workers=2)

def get_memory(conversation_id: str) -> ConversationBufferMemory:
    if conversation_id not in conversation_memories:
        conversation_memories[conversation_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key='answer'
        )
    return conversation_memories[conversation_id]

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""
    أجب فقط من المعلومات التالية كمُعلم في مدرسة. إذا لم تجد الجواب فيها، قل "لم يتم العثور على إجابة."
    ----
    {context}
    ----
    السؤال: {question}
    الجواب:
    """
)



@app.on_event("startup")
async def startup_event():
    temp_dir = tempfile.gettempdir()
    for filename in os.listdir(temp_dir):
        if filename.endswith(".wav"):
            try:
                os.remove(os.path.join(temp_dir, filename))
            except Exception:
                pass

@app.on_event("shutdown")
def shutdown_event():
    executor.shutdown()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

async def process_question(question: str, conversation_id: str, db_path: str, teacher: str) -> Dict:
    db = FAISS.load_local(db_path, embedding_model, allow_dangerous_deserialization=True)
    retriever = db.as_retriever()
    memory = get_memory(conversation_id)

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=False,
        combine_docs_chain_kwargs={'prompt': QA_PROMPT}
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        lambda: qa_chain({"question": question})
    )

    answer = result["answer"].strip()
    if "لم يتم العثور على إجابة" in answer or answer == "" or answer.lower().startswith("عذرًا") or answer.lower().startswith("عذرا"):
        response = "لم يتم العثور على إجابة."
    else:
        response = f"{teacher} يرد:\n{answer}"

    if conversation_id not in chat_histories:
        chat_histories[conversation_id] = []
    chat_histories[conversation_id].append({
        "question": question,
        "answer": response
    })

    timestamp = int(time.time() * 1000)
    audio_file_name = f"teacher_response_{conversation_id}_{timestamp}.mp3"
    audio_dir = "static/audio"
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, audio_file_name)
    azure_text_to_speech(answer, audio_path)

    return {
        "answer": response,
        "audio_file": audio_file_name,
        "conversation_id": conversation_id
    }

@app.post("/ask")
async def ask_question(request: Request, question: str = Form(...)):
    conversation_id = request.headers.get("X-Conversation-ID", str(uuid4()))
    # 1. Route using LLM agent
    subject = route_subject_with_llm(question)
    if subject not in subject_db_map:
        return JSONResponse({"answer": "لم يتم العثور على إجابة."})
    db_path, teacher = subject_db_map[subject]
    # 2. Normal flow
    try:
        result = await process_question(question, conversation_id, db_path, teacher)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/record")
async def record_voice(request: Request, audio: UploadFile = File(...)):
    conversation_id = request.headers.get("X-Conversation-ID", str(uuid4()))
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"recording_{conversation_id}.wav")
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await audio.read()
            await out_file.write(content)
        model = whisper.load_model("base")
        result = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: model.transcribe(file_path, language="ar")
        )
        transcript = result["text"].strip()
        if not transcript:
            return JSONResponse({"error": "لم يتم التعرف على كلام"}, status_code=400)
        # Route with LLM
        subject = route_subject_with_llm(transcript)
        if subject not in subject_db_map:
            return JSONResponse({"answer": "لم يتم العثور على إجابة."})
        db_path, teacher = subject_db_map[subject]
        qa_result = await process_question(transcript, conversation_id, db_path, teacher)
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"خطأ في حذف الملف المؤقت: {e}")
        return JSONResponse({
            "transcript": transcript,
            "answer": qa_result.get("answer", "لا توجد إجابة"),
            "audio_file": qa_result.get("audio_file", "")
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/history")
async def get_history(request: Request):
    conversation_id = request.headers.get("X-Conversation-ID")
    if not conversation_id or conversation_id not in chat_histories:
        return JSONResponse({"history": []})
    return JSONResponse({"history": chat_histories[conversation_id]})

@app.post("/reset")
async def reset_chat(request: Request):
    conversation_id = request.headers.get("X-Conversation-ID")
    if conversation_id in conversation_memories:
        del conversation_memories[conversation_id]
    if conversation_id in chat_histories:
        del chat_histories[conversation_id]
    return JSONResponse({"status": "تم مسح المحادثة والتخزين المؤقت"})

@app.get("/export", response_class=FileResponse)
async def export_chat(request: Request):
    conversation_id = request.headers.get("X-Conversation-ID")
    if not conversation_id or conversation_id not in chat_histories:
        return JSONResponse({"error": "لا توجد محادثة لهذا المعرف"}, status_code=404)

    history = chat_histories[conversation_id]
    export_text = ""
    for item in history:
        export_text += f"أنت: {item['question']}\n{item['answer']}\n\n"

    tmp_path = os.path.join(tempfile.gettempdir(), f"chat_{conversation_id}.txt")
    async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
        await f.write(export_text)

    return FileResponse(
        path=tmp_path,
        filename="محادثة_مجلس_المعلمين.txt",
        media_type="text/plain"
    )

@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    يستقبل ملف صوتي (audio) ويعيد النصّ فقط دون إجراء البحث.
    """
    # 1) حفظ الملف مؤقتًا
    tmp_dir = tempfile.gettempdir()
    wav_path = os.path.join(tmp_dir, f"{uuid4()}.webm")  # أو .wav إذا أردتِ

    async with aiofiles.open(wav_path, "wb") as f:
        await f.write(await audio.read())

    # 2) استدعاء Whisper للتفريغ النصّي
    model = whisper.load_model("small")
    result = model.transcribe(wav_path, language="ar")
    transcript = result["text"].strip()

    # 3) حذف الملف المؤقت
    try:
        os.remove(wav_path)
    except:
        pass

    # 4) إرجاع النص فقط بصيغة JSON
    return JSONResponse({"transcript": transcript})