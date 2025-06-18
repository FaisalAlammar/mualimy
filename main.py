from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
import platform

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
import arabic_reshaper
from bidi.algorithm import get_display


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
        print(" تم توليد الرد الصوتي .")
    else:
        print(f" خطأ في تحويل النص إلى صوت: {response.status_code}")
        print(response.text)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

llm = Ollama(
    model="command-r7b-arabic",
    temperature=0.3,
    num_ctx=2048,
    num_thread=4
)

# Use Ollama as the subject router
def route_subject_with_llm(question: str) -> str:
    router_prompt = (
        "أنت مسؤول عن توجيه الأسئلة إلى أحد المواد التالية فقط: فيزياء، كيمياء، أحياء.\n"
        "إذا لم يكن السؤال متعلقًا بأي من هذه المواد، أجب فقط بـ: 'غير معروف'.\n"
        f"السؤال: {question}\n"
        "الموضوع:"
    )
    response = llm(router_prompt)
    subject = response.strip().replace(" ", "").replace(":", "").lower()

    if "فيزياء" in subject:
        return "physics"
    if "كيمياء" in subject:
        return "chemistry"
    if "أحياء" in subject or "احياء" in subject:
        return "biology"

    # Explicit fallback if subject is unknown or not one of the three
    return "unknown"

subject_db_map = {
    "physics":    ("db_physics",   "معلم الفيزياء"),
    "chemistry":  ("db_chemistry", "معلم الكيمياء"),
    "biology":    ("db_biology",   "معلم الأحياء"),
}

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/distiluse-base-multilingual-cased-v1"
)

conversation_memories: Dict[str, ConversationBufferMemory] = {}
chat_histories: Dict[str, List[Dict]] = {}
conversation_subjects: Dict[str, str] = {}
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
    clean_answer = answer.replace("**", "")
    clean_answer = clean_answer.replace("###", "")
    azure_text_to_speech(answer, audio_path)

    return {
        "answer": response,
        "audio_file": audio_file_name,
        "conversation_id": conversation_id
    }

def find_image_for_answer(answer: str, question: str, subject: str) -> str | None:
    image_map = {
        "physics": {

            "السقوط الحر":              "static/topic_images/physics/free_fall.jpg",
            "القوة والحركة":           "static/topic_images/physics/force_motion.jpg",
            "السرعة المنتظمة":         "static/topic_images/physics/uniform_velocity.jpg",
            "قانون نيوتن الثالث":     "static/topic_images/physics/third_law.jpg",
            "الاحتكاك":         		"static/topic_images/physics/friction.jpg",
            "القوة العمودية":         "static/topic_images/physics/perpendicular_force.jpg",

        },
        "biology": {
            "البكتيريا":             "static/topic_images/biology/bacteria.jpg",
            "الفيروسات":             "static/topic_images/biology/viruses.jpg",
            "الفطريات":              "static/topic_images/biology/fungi.jpg",
            "المفصليات":             "static/topic_images/biology/arthropods.jpg",
            "الخلية":                "static/topic_images/biology/cell.jpg",
        },
        "chemistry": {
            "الجدول الدوري":         "static/topic_images/chemistry/periodic_table.jpg",
            "الروابط التساهمية":     "static/topic_images/chemistry/covalent_bonds.jpg",
            "الذرة":                  "static/topic_images/chemistry/atom.jpg",
            "العنصر":                 "static/topic_images/chemistry/element.jpg",
            "المركب":                 "static/topic_images/chemistry/compound.jpg",
        }
    }
    q = question.lower()

    # نبحث فقط في السؤال، مع التأكيد على استخدام dict كافتراضي
    for keyword, img_path in image_map.get(subject, {}).items():
        if keyword in q:
            return img_path if img_path.startswith("/") else f"/{img_path}"
    return None


@app.post("/ask")
async def ask_question(request: Request, question: str = Form(...)):
    conversation_id = request.headers.get("X-Conversation-ID", str(uuid4()))

    routed = route_subject_with_llm(question)
    if routed in subject_db_map:
        subject = routed
        conversation_subjects[conversation_id] = subject
    else:
        if conversation_id not in conversation_subjects:
            return StreamingResponse(
                iter(["الاجابة ليست متوفرة بالمنهج."]),
                media_type="text/plain"
            )
        subject = conversation_subjects[conversation_id]
    if subject == "unknown" or subject not in subject_db_map:
        return StreamingResponse(iter(["الاجابة ليست متوفرة بالمنهج."]), media_type="text/plain")
    
    JSONResponse({
            "answer": "لم يتم العثور على إجابة.",
            "audio_file": "",
            "conversation_id": conversation_id,
            "images": []
        })

    db_path, teacher = subject_db_map[subject]

    # 2. Normal flow
    try:
        async def generate_response():
            result = await process_question(question, conversation_id, db_path, teacher)
            full_text = result["answer"]
            audio_file = result["audio_file"]

                    # **هنا** نستخدم الـ subject لمعرفة الصورة
            img = find_image_for_answer(full_text, question, subject)
            images = [img] if img else []
            
            # Streaming Response Text
            for char in full_text:
                yield char
                # Sleep Time
                await asyncio.sleep(0.01)

            # نهاية: نضيف فاصل مميز لتُستخدم في JS لاستخراج audio_file
            yield f"\n[AUDIO_FILE:{audio_file}]"

            if images:
            # دمج روابط الصور بفاصلة
                imgs_str = ",".join(images)
                yield f"\n[IMAGES:{imgs_str}]"



        return StreamingResponse(generate_response(), media_type="text/plain")

    except Exception as e:
        return StreamingResponse(iter([f"حدث خطأ: {str(e)}"]), media_type="text/plain")


@app.post("/record")
async def record_voice(request: Request, audio: UploadFile = File(...)):
    conversation_id = request.headers.get("X-Conversation-ID", str(uuid4()))
    try:
        # حفظ الملف مؤقتاً
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"recording_{conversation_id}.wav")
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(await audio.read())

        # تفريغ النص
        model = whisper.load_model("base")
        result = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: model.transcribe(file_path, language="ar")
        )
        transcript = result["text"].strip()
        if not transcript:
            return JSONResponse({"error": "لم يتم التعرف على كلام"}, status_code=400)

        # تحديد الموضوع
        subject = route_subject_with_llm(transcript)
        if subject not in subject_db_map:
            # حتى لو ما فيه subject، نرجّع JSON متوحد الشكل
            return JSONResponse({
                "transcript": transcript,
                "answer": "لم يتم العثور على إجابة.",
                "audio_file": "",
                "images": []
            })

        # جلب الجواب
        db_path, teacher = subject_db_map[subject]
        qa_result = await process_question(transcript, conversation_id, db_path, teacher)

        # اختيار الصورة المناسبة
        img = find_image_for_answer(qa_result["answer"], transcript, subject)

        # حذف الملف المؤقت
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"خطأ في حذف الملف المؤقت: {e}")

        # إرجاع JSON مع images
        return JSONResponse({
            "transcript": transcript,
            "answer": qa_result.get("answer", "لا توجد إجابة"),
            "audio_file": qa_result.get("audio_file", ""),
            "images": [img] if img else []
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

    font_path = ("C:/Windows/Fonts/arial.ttf" if platform.system() == "Windows"
                 else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont("Arabic", font_path))

    tmp_path = os.path.join(tempfile.gettempdir(), f"chat_{conversation_id}.pdf")
    c = canvas.Canvas(tmp_path, pagesize=A4)
    page_width, page_height = A4
    margin = 40
    usable_width = page_width - 2 * margin
    x = page_width - margin
    y = page_height - 80
    page_number = 1

    def draw_header():
        nonlocal y
        y = page_height - 80
        c.setFont("Arabic", 16)
        title = get_display(arabic_reshaper.reshape("محادثة مُعلّمي"))
        c.drawCentredString(page_width / 2, y, title)
        y -= 10
        c.line(margin, y, page_width - margin, y)
        y -= 30

    def draw_footer():
        c.setFont("Arabic", 12)
        c.line(margin, 50, page_width - margin, 50)
        c.drawCentredString(page_width / 2, 35, str(page_number))

    def write_wrapped_text(text, line_height):
        nonlocal y, page_number
        c.setFont("Arabic", 14)
        words = text.split()
        lines = []
        current_line = ""
        for word in reversed(words):
            test_line = f"{word} {current_line}".strip()
            if pdfmetrics.stringWidth(test_line, "Arabic", 14) < usable_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        lines = list(reversed(lines))

        for line in lines:
            if y < 70:
                draw_footer()
                c.showPage()
                page_number += 1
                draw_header()
            c.drawRightString(x, y, line)
            y -= line_height

    draw_header()

    for item in history:
        question = item['question']
        reshaped_q = get_display(arabic_reshaper.reshape(question))
        write_wrapped_text(reshaped_q, 22)

        for line in item['answer'].split('\n'):
            clean = line.strip()
            if clean:
                reshaped = get_display(arabic_reshaper.reshape(clean))
                write_wrapped_text(reshaped, 20)

        y -= 40
        if y < 70:
            draw_footer()
            c.showPage()
            page_number += 1
            draw_header()

    draw_footer()
    c.save()

    return FileResponse(path=tmp_path, filename="محادثة_معلمي.pdf", media_type="application/pdf")


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
