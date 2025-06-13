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
  const box = document.getElementById("chat-box");
  let loader = document.createElement("div");
  loader.className = "message teacher";
  loader.id = "loader-message";
  loader.innerHTML = '<span class="loader"></span> جاري المعالجة ...';
  box.appendChild(loader);
  box.scrollTop = box.scrollHeight;
}
function removeLoader() {
  let loader = document.getElementById("loader-message");
  if (loader) loader.remove();
}

function addToChat(sender, message, audioFile = null) {
  const welcome = document.getElementById("welcome-message");
  if (welcome) welcome.remove();

  const box = document.getElementById("chat-box");
  const msg = document.createElement("div");
  msg.className = sender === "أنت" ? "message user" : "message teacher";
  msg.style.display = "flex";
  msg.style.alignItems = "flex-start";
  msg.style.direction = "rtl";

  if (audioFile && sender !== "أنت") {
    const playBtn = document.createElement("button");
    playBtn.className = "audio-icon-btn";
    playBtn.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 20 20" style="vertical-align: middle;">
        <circle cx="10" cy="10" r="10" fill="#3B2785"/>
        <polygon points="7,6 15,10 7,14" fill="#fff"/>
      </svg>
    `;
    playBtn.title = "تشغيل الصوت";
    playBtn.style.marginLeft = "8px";
    playBtn.style.marginRight = "2px";

    const audio = new Audio(`/static/audio/${audioFile}?t=${Date.now()}`);
    playBtn.onclick = function() {
      if (!audio.paused) {
        audio.pause();
        audio.currentTime = 0;
        playBtn.innerHTML = `
          <svg width="22" height="22" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
            <polygon points="7,6 15,10 7,14" fill="#fff"/>
          </svg>
        `;
      } else {
        audio.play();
        playBtn.innerHTML = `
          <svg width="22" height="22" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
            <rect x="7" y="6" width="2" height="8" fill="#fff"/>
            <rect x="11" y="6" width="2" height="8" fill="#fff"/>
          </svg>
        `;
      }
    };
    audio.onended = () => {
      playBtn.innerHTML = `
        <svg width="22" height="22" viewBox="0 0 20 20">
          <circle cx="10" cy="10" r="10" fill="#6a39b2"/>
          <polygon points="7,6 15,10 7,14" fill="#fff"/>
        </svg>
      `;
    };
    msg.appendChild(playBtn);
  }

  const msgText = document.createElement("span");
  msgText.textContent = message;
  msgText.style.flex = "1";
  msgText.style.display = "block";
  msg.appendChild(msgText);

  box.appendChild(msg);
  box.scrollTop = box.scrollHeight;
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

  // Streaming Response (NEW)
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullText = "";
  let audioFile = null;

  const teacherMsg = document.createElement("div");
  teacherMsg.className = "message teacher";
  teacherMsg.style.display = "flex";
  teacherMsg.style.alignItems = "flex-start";
  teacherMsg.style.direction = "rtl";
  const msgText = document.createElement("span");
  msgText.style.flex = "1";
  msgText.style.display = "block";
  teacherMsg.appendChild(msgText);
  chatBox.appendChild(teacherMsg);
  chatBox.scrollTop = chatBox.scrollHeight;
  
  let loaderRemoved = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    
     if (!loaderRemoved && chunk.trim()) {
    removeLoader();         // نحذف "جاري المعالجة" أول ما يبدأ الرد
    loaderRemoved = true;   // نضمن أنها تنفذ مرة واحدة فقط
  }
    
    fullText += chunk;
    

    if (chunk.includes("[AUDIO_FILE:")) {
      const match = chunk.match(/\[AUDIO_FILE:(.*?)\]/);
      if (match) {
        audioFile = match[1].trim();
        msgText.textContent = fullText.replace(match[0], "").trim();
      }
    } else {
      for (let char of chunk) {
  msgText.textContent += char;
  await new Promise(resolve => setTimeout(resolve, 8));
}

    }

    chatBox.scrollTop = chatBox.scrollHeight;
  }

  removeLoader();

  if (audioFile) {
    const playBtn = document.createElement("button");
playBtn.className = "audio-icon-btn";
playBtn.innerHTML = `
  <svg width="22" height="22" viewBox="0 0 20 20">
    <circle cx="10" cy="10" r="10" fill="#3B2785"/>
    <polygon points="7,6 15,10 7,14" fill="#fff"/>
  </svg>
`;

const audio = new Audio(`/static/audio/${audioFile}?t=${Date.now()}`);
playBtn.onclick = function () {
  if (!audio.paused) {
    audio.pause();
    audio.currentTime = 0;
    playBtn.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 20 20">
        <circle cx="10" cy="10" r="10" fill="#3B2785"/>
        <polygon points="7,6 15,10 7,14" fill="#fff"/>
      </svg>
    `;
  } else {
    audio.play();
    playBtn.innerHTML = `
      <svg width="22" height="22" viewBox="0 0 20 20">
        <circle cx="10" cy="10" r="10" fill="#3B2785"/>
        <rect x="7" y="6" width="2" height="8" fill="#fff"/>
        <rect x="11" y="6" width="2" height="8" fill="#fff"/>
      </svg>
    `;
  }
};
audio.onended = () => {
  playBtn.innerHTML = `
    <svg width="22" height="22" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="10" fill="#3B2785"/>
      <polygon points="7,6 15,10 7,14" fill="#fff"/>
    </svg>
  `;
};

teacherMsg.insertBefore(playBtn, msgText);

  }
});


document.getElementById("voice-btn").addEventListener("click", async function() {
  const button = this;
  button.disabled = true;

  let stream = null;
  let recorder = null;

  try {
        // 🧽 إزالة رسالة الترحيب مباشرة بعد بداية التسجيل
    const welcome = document.getElementById("welcome-message");
    if (welcome) welcome.remove();
    
    // 1) طلب إذن الميكروفون وبدء التسجيل
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    const chunks = [];

    recorder.addEventListener('dataavailable', (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    });

    recorder.addEventListener('stop', async () => {
      // 2) أوقف الميكروفون فعلياً لتحريره
      stream.getTracks().forEach(track => track.stop());

      // 3) أضف رسالة "جاري التعرف على الصوت..." بشكل مؤقت
      const chatBox = document.getElementById("chat-box");
      const tempMsg = document.createElement("div");
      tempMsg.id = "transcribing-temp";
      tempMsg.className = "message user";
      tempMsg.style.display = "flex";
      tempMsg.style.alignItems = "flex-start";
      tempMsg.style.direction = "rtl";
      tempMsg.textContent = "جاري التعرف على الصوت...";
      chatBox.appendChild(tempMsg);
      chatBox.scrollTop = chatBox.scrollHeight;

      // 4) اجمع القطع في Blob بصيغة WebM
      const audioBlob = new Blob(chunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");

      // 5) أرسل الصوت أولاً لـ /transcribe للحصول على النص فقط
      let transcript = "";
      try {
        const tResp = await fetch("/transcribe", {
          method: "POST",
          body: formData
        });
        const tData = await tResp.json();
        transcript = tData.transcript?.trim() || "";
      } catch (e) {
        console.error("خطأ في التفريغ النصّي:", e);
        transcript = "";
      }

      // 6) احذف رسالة "جاري التعرف على الصوت..."
      const existingTemp = document.getElementById("transcribing-temp");
      if (existingTemp) {
        existingTemp.remove();
      }

      // 7) عرض السؤال الفعلي كرسالة في الشات
      if (transcript) {
        addToChat("أنت", transcript);
      } else {
        addToChat("أنت", "[لم يُتم التعرف على الصوت]");
      }

      // 8) الآن نُظهر الرسالة “جاري المعالجة...”
      showLoader();

      // 9) نرسل النص نفسه لـ /ask للحصول على الإجابة
      try {
        const aResp = await fetch("/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Conversation-ID": conversationId
          },
          body: `question=${encodeURIComponent(transcript)}`
        });
        const aData = await aResp.json();
        removeLoader();

        if (aData.error) {
          addToChat("المعلم", "حدث خطأ: " + aData.error);
        } else {
          addToChat("المعلم", aData.answer, aData.audio_file);
        }
      } catch (e) {
        removeLoader();
        console.error("خطأ في جلب الإجابة:", e);
        addToChat("المعلم", "حدث خطأ أثناء جلب الإجابة.");
      }

      // 10) أعد تمكين الزر ونصّه إلى الأيقونة الأصلية
      button.disabled = false;
    });

    // 11) ابدأ التسجيل وتوقّفه بعد 5 ثواني
    recorder.start();
    setTimeout(() => {
      if (recorder && recorder.state !== "inactive") {
        recorder.stop();
      }
    }, 5000);

  } catch (error) {
    console.error("خطأ أثناء التسجيل:", error);
    alert("حدث خطأ أثناء محاولة التسجيل بالصوت.");
    // تأكد من إيقاف الميكروفون في حال حدوث خطأ
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }
    button.disabled = false;
  }
});


// إعادة التعيين
document.getElementById("reset-btn").addEventListener("click", async function() {
  conversationId = Date.now().toString();  // إنشاء معرف جديد
  localStorage.setItem('conversationId', conversationId);

  await fetch("/reset", {
    method: "POST",
    headers: {
      "X-Conversation-ID": conversationId
    }
  });
  document.getElementById("chat-box").innerHTML = "";
  const welcomeMsg = document.createElement("div");
  welcomeMsg.id = "welcome-message";
  welcomeMsg.textContent = "مرحبًا بِك في مُعلِمي, كيف أُساعدك اليوم؟";
  welcomeMsg.style.textAlign = "center";
  welcomeMsg.style.color = "#4931AF";
  welcomeMsg.style.marginTop = "143px";
  welcomeMsg.style.fontSize = "2rem";
  welcomeMsg.style.fontWeight = "bold";
  chatBox.appendChild(welcomeMsg);
});

document.getElementById("download-btn").addEventListener("click", () => {
  fetch("/export", {
    method: "GET",
    headers: {
      "X-Conversation-ID": conversationId
    }
  })
    .then(response => {
      if (!response.ok) throw new Error("فشل في تحميل الملف");
      return response.blob();
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "محادثة_معلمي.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    })
    .catch(err => {
      alert("حدث خطأ أثناء تصدير المحادثة: " + err.message);
    });
});