// إعداد معرف المحادثة
let conversationId = localStorage.getItem('conversationId') || Date.now().toString();
localStorage.setItem('conversationId', conversationId);

// إضافة رسالة ترحيبية في البداية
const chatBox = document.getElementById("chat-box");
const welcomeMsg = document.createElement("div");
welcomeMsg.id = "welcome-message";
welcomeMsg.className = "welcome-message";
welcomeMsg.textContent = "مرحبًا بِك في مُعلِمي, كيف أُساعدك اليوم؟";
welcomeMsg.style.setProperty("color", "#5f259f", "important");
chatBox.appendChild(welcomeMsg);

// Loader
function showLoader() {
  const loader = document.createElement("div");
  loader.className = "message teacher";
  loader.id = "loader-message";
  loader.innerHTML = '<span class="loader"></span> جاري المعالجة ...';
  chatBox.appendChild(loader);
  chatBox.scrollTop = chatBox.scrollHeight;
}
function removeLoader() {
  const loader = document.getElementById("loader-message");
  if (loader) loader.remove();
}

// دالة الإضافة إلى الشات مع دعم الصوت، النص، والصورة
function addToChat(sender, message, audioFile = null, images = []) {
  // إزالة رسالة الترحيب عند أول إضافة
  const wm = document.getElementById("welcome-message");
  if (wm) wm.remove();

  const msg = document.createElement("div");
  msg.className = sender === "أنت" ? "message user" : "message teacher";
  msg.style.display = "flex";
  msg.style.alignItems = "flex-start";
  msg.style.direction = "rtl";

  // زر تشغيل الصوت (إن وُجد)
  if (audioFile && sender !== "أنت") {
    const playBtn = document.createElement("button");
    playBtn.className = "audio-icon-btn";
    playBtn.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 20 20">
        <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
        <polygon points="7,6 15,10 7,14" fill="#fff"/>
      </svg>`;
    playBtn.style.marginRight = "8px";
    const audio = new Audio(`/static/audio/${audioFile}?t=${Date.now()}`);
    playBtn.onclick = () => {
      if (!audio.paused) { audio.pause(); audio.currentTime = 0; }
      else { audio.play(); }
    };
    audio.onended = () => {
      playBtn.innerHTML = `
        <svg width="22" height="22" viewBox="0 0 20 20">
          <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
          <polygon points="7,6 15,10 7,14" fill="#fff"/>
        </svg>`;
    };
    msg.appendChild(playBtn);
  }

  // نص الرسالة
  const textSpan = document.createElement("span");
  textSpan.textContent = message;
  textSpan.style.flex = "1";
  textSpan.style.display = "block";
  msg.appendChild(textSpan);

  // عرض الصور إن وجدت
  if (images.length) {
    const imgContainer = document.createElement("div");
    imgContainer.classList.add("chat-img-container");
    images.forEach(src => {
      const img = document.createElement("img");
      img.src = src; // مثال: "/static/topic_images/biology/cell.jpg"
      img.classList.add("chat-image");
      imgContainer.appendChild(img);
    });
    msg.appendChild(imgContainer);
  }

  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// إرسال الأسئلة النصية
document.getElementById("chat-form").addEventListener("submit", async function(e) {
  e.preventDefault();
  const input = document.getElementById("question");
  const question = input.value.trim();
  if (!question) return;

  addToChat("أنت", question);
  input.value = "";

  showLoader();
  const response = await fetch("/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-Conversation-ID": conversationId
    },
    body: "question=" + encodeURIComponent(question)
  });

  // Streaming Response
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullText = "", audioFile = null, images = [];

  // إعداد عنصر المعلم
  const teacherMsg = document.createElement("div");
  teacherMsg.className = "message teacher";
  teacherMsg.style.display = "flex";
  teacherMsg.style.alignItems = "flex-start";
  teacherMsg.style.direction = "rtl";
 

  const msgText = document.createElement("span");
  msgText.style.flex = "1";
  msgText.style.display = "block";
  teacherMsg.appendChild(msgText);

  let loaderRemoved = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);

    if (!loaderRemoved && chunk.trim()) {
      removeLoader();
      chatBox.appendChild(teacherMsg);
      chatBox.scrollTop = chatBox.scrollHeight;
      loaderRemoved = true;
    }

    fullText += chunk;

    // استخراج الصوت
    if (chunk.includes("[AUDIO_FILE:")) {
      const m = chunk.match(/\[AUDIO_FILE:(.*?)\]/);
      if (m) {
        audioFile = m[1].trim();
        msgText.textContent = fullText.replace(m[0], "").trim();
      }
    }
    // استخراج الصور
    if (chunk.includes("[IMAGES:")) {
      const matchImg = chunk.match(/\[IMAGES:(.*?)\]/);
      if (matchImg) {
        const imgSrc = matchImg[1].trim();
        // إزالة العلامة من النص
        msgText.textContent = msgText.textContent.replace(matchImg[0], "").trim();
        // إضافة الرابط إلى قائمة الصور
        images.push(imgSrc);
      }
    }
    // بقية النص
    if (!chunk.includes("[AUDIO_FILE:") && !chunk.includes("[IMAGES:")) {
      for (const c of chunk) {
        msgText.textContent += c;
        await new Promise(r => setTimeout(r, 8));
      }
    }

    chatBox.scrollTop = chatBox.scrollHeight;
  }

  removeLoader();
  // إضافة الصور داخل الرسالة
  if (images.length) {
    const imgContainer = document.createElement("div");
    imgContainer.classList.add("chat-img-container");
    images.forEach(src => {
      const img = document.createElement("img");
      img.src = src;
      img.classList.add("chat-image");
      imgContainer.appendChild(img);
    });
    teacherMsg.appendChild(imgContainer);
  }
  // إضافة زر الصوت
if (audioFile) {
    const playBtn = document.createElement("button");
    playBtn.className = "audio-icon-btn";

    const playIcon = `
      <svg width="22" height="22" viewBox="0 0 20 20">
        <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
        <polygon points="7,6 15,10 7,14" fill="#fff"/>
      </svg>`;
    const pauseIcon = `
      <svg width="22" height="22" viewBox="0 0 20 20">
        <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
        <rect x="6" y="6" width="3" height="8" fill="#fff"/>
        <rect x="11" y="6" width="3" height="8" fill="#fff"/>
      </svg>`;

    // نستخدم playIcon كبداية
    playBtn.innerHTML = playIcon;
    const audio = new Audio(`/static/audio/${audioFile}?t=${Date.now()}`);

    // ربط حدث النقر للتشغيل/الإيقاف وتبديل الأيقونة
    playBtn.addEventListener("click", () => {
      if (audio.paused) {
        audio.play();
        playBtn.innerHTML = pauseIcon;
      } else {
        audio.pause();
        audio.currentTime = 0;  // إعادة الصوت للبداية
        playBtn.innerHTML = playIcon;
      }
    });

    // أدخل الزر قبل نص الرسالة في الـ DOM
    teacherMsg.insertBefore(playBtn, msgText);
  }
});


// تسجيل بالصوت: تعبئة السؤال ثم إعادة إرسال النموذج
document.getElementById("voice-btn").addEventListener("click", async function() {
  const btn = this; btn.disabled = true;
  let stream, recorder;
  try {
    const welcome = document.getElementById("welcome-message"); if (welcome) welcome.remove();
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    const chunks = [];
    recorder.addEventListener('dataavailable', e => { if (e.data.size) chunks.push(e.data); });
    recorder.addEventListener('stop', async () => {
      stream.getTracks().forEach(t => t.stop());
      const temp = document.createElement("div"); temp.id="transcribing-temp"; temp.className="message user";
      temp.style.direction="rtl"; temp.textContent="جاري التعرف على الصوت...";
      chatBox.appendChild(temp); chatBox.scrollTop=chatBox.scrollHeight;
      const blob = new Blob(chunks, { type: 'audio/webm' });
      const formTrans = new FormData(); formTrans.append("audio", blob, "recording.webm");
      let transcript = "";
      try { const tResp = await fetch("/transcribe", { method: "POST", body: formTrans }); transcript = (await tResp.json()).transcript.trim(); } catch {}
      temp.remove();
      document.getElementById("question").value = transcript;
      document.getElementById("chat-form").requestSubmit();
      btn.disabled = false;
    });
    recorder.start(); setTimeout(() => recorder.state !== "inactive" && recorder.stop(), 5000);
  } catch (err) {
    console.error(err); alert("خطأ أثناء التسجيل."); if (stream) stream.getTracks().forEach(t => t.stop()); btn.disabled = false;
  }
});

// إعادة التعيين
document.getElementById("reset-btn").addEventListener("click", async function() {
  conversationId = Date.now().toString(); localStorage.setItem('conversationId', conversationId);
  await fetch("/reset", { method: "POST", headers: { "X-Conversation-ID": conversationId } });
  chatBox.innerHTML = "";
  const wm = document.createElement("div"); wm.id = "welcome-message"; wm.className = "welcome-message";
  wm.textContent = "مرحبًا بِك في مُعلِمي, كيف أُساعدك اليوم؟";
  wm.style.cssText = "text-align:center;color:#4931AF;margin-top:143px;font-size:2rem;font-weight:bold;";
  chatBox.appendChild(wm);
});

// تحميل المحادثة كـPDF
document.getElementById("download-btn").addEventListener("click", () => {
  fetch("/export", { method: "GET", headers: { "X-Conversation-ID": conversationId } })
    .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "محادثة_معلمي.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
    })
    .catch(e => alert("خطأ في تصدير: " + e.message));
});
