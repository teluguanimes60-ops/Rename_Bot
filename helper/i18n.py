from __future__ import annotations

LANGUAGES = [
    ("ar", "Arabic", "🇦🇪"), ("hy", "Armenian", "🇦🇲"), ("az", "Azerbaijani", "🇦🇿"),
    ("bn", "Bengali", "🇧🇩"), ("bg", "Bulgarian", "🇧🇬"), ("zh", "Chinese", "🇨🇳"),
    ("hr", "Croatian", "🇭🇷"), ("cs", "Czech", "🇨🇿"), ("da", "Danish", "🇩🇰"),
    ("nl", "Dutch", "🇳🇱"), ("en", "English", "🇬🇧"), ("fi", "Finnish", "🇫🇮"),
    ("fr", "French", "🇫🇷"), ("ka", "Georgian", "🇬🇪"), ("de", "German", "🇩🇪"),
    ("el", "Greek", "🇬🇷"), ("he", "Hebrew", "🇮🇱"), ("hi", "Hindi", "🇮🇳"),
    ("hu", "Hungarian", "🇭🇺"), ("id", "Indonesian", "🇮🇩"), ("it", "Italian", "🇮🇹"),
    ("ja", "Japanese", "🇯🇵"), ("kk", "Kazakh", "🇰🇿"), ("ko", "Korean", "🇰🇷"),
    ("ms", "Malay", "🇲🇾"), ("ml", "Malayalam", "🇮🇳"), ("mr", "Marathi", "🇮🇳"),
    ("ne", "Nepali", "🇳🇵"), ("no", "Norwegian", "🇳🇴"), ("or", "Odia", "🇮🇳"),
    ("fa", "Persian", "🇮🇷"), ("fil", "Filipino", "🇵🇭"), ("pl", "Polish", "🇵🇱"),
    ("pt", "Portuguese", "🇵🇹"), ("pa", "Punjabi", "🇮🇳"), ("ro", "Romanian", "🇷🇴"),
    ("ru", "Russian", "🇷🇺"), ("sr", "Serbian", "🇷🇸"), ("sk", "Slovak", "🇸🇰"),
    ("sl", "Slovenian", "🇸🇮"), ("es", "Spanish", "🇪🇸"), ("si", "Sinhala", "🇱🇰"),
    ("sv", "Swedish", "🇸🇪"), ("th", "Thai", "🇹🇭"), ("ta", "Tamil", "🇮🇳"),
    ("te", "Telugu", "🇮🇳"), ("tr", "Turkish", "🇹🇷"), ("uk", "Ukrainian", "🇺🇦"),
    ("ur", "Urdu", "🇵🇰"), ("uz", "Uzbek", "🇺🇿"), ("vi", "Vietnamese", "🇻🇳"),
]

_LANGUAGE_MAP = {code: {"name": name, "flag": flag} for code, name, flag in LANGUAGES}
DEFAULT_LANGUAGE = "en"

_TRANSLATIONS = {
    "en": {
        "select_title": "🌐 **Select Your Language**",
        "select_prompt": "Choose the language you want to use for AniToon Bot messages.",
        "confirm": "✅ Confirm",
        "language_saved": "✅ Language saved successfully.",
        "settings_language": "🌐 Language",
        "settings_title": "⚙️ **AniToon Settings**",
        "settings_choose": "Choose what you want to manage:",
        "back": "🔙 Back",
        "language_changed": "✅ Language changed successfully.",
    },
    "ar": {"select_title":"🌐 **اختر لغتك**","select_prompt":"اختر اللغة التي تريد استخدامها لرسائل AniToon Bot.","confirm":"✅ تأكيد","language_saved":"✅ تم حفظ اللغة بنجاح.","settings_language":"🌐 اللغة","settings_title":"⚙️ **إعدادات AniToon**","settings_choose":"اختر ما تريد إدارته:","back":"🔙 رجوع","language_changed":"✅ تم تغيير اللغة بنجاح."},
    "hy": {"select_title":"🌐 **Ընտրեք ձեր լեզուն**","select_prompt":"Ընտրեք լեզուն, որը ցանկանում եք օգտագործել AniToon Bot-ի հաղորդագրությունների համար։","confirm":"✅ Հաստատել","language_saved":"✅ Լեզուն հաջողությամբ պահպանվեց։","settings_language":"🌐 Լեզու","settings_title":"⚙️ **AniToon-ի կարգավորումներ**","settings_choose":"Ընտրեք, թե ինչ եք ցանկանում կառավարել։","back":"🔙 Հետ","language_changed":"✅ Լեզուն հաջողությամբ փոխվեց։"},
    "az": {"select_title":"🌐 **Dil seçin**","select_prompt":"AniToon Bot mesajları üçün istifadə etmək istədiyiniz dili seçin.","confirm":"✅ Təsdiq et","language_saved":"✅ Dil uğurla yadda saxlanıldı.","settings_language":"🌐 Dil","settings_title":"⚙️ **AniToon Parametrləri**","settings_choose":"Nəyi idarə etmək istədiyinizi seçin:","back":"🔙 Geri","language_changed":"✅ Dil uğurla dəyişdirildi."},
    "bn": {"select_title":"🌐 **আপনার ভাষা নির্বাচন করুন**","select_prompt":"AniToon Bot-এর বার্তাগুলোর জন্য আপনি যে ভাষা ব্যবহার করতে চান তা নির্বাচন করুন।","confirm":"✅ নিশ্চিত করুন","language_saved":"✅ ভাষা সফলভাবে সংরক্ষণ করা হয়েছে।","settings_language":"🌐 ভাষা","settings_title":"⚙️ **AniToon সেটিংস**","settings_choose":"আপনি কী পরিচালনা করতে চান তা নির্বাচন করুন:","back":"🔙 পিছনে","language_changed":"✅ ভাষা সফলভাবে পরিবর্তন হয়েছে।"},
    "bg": {"select_title":"🌐 **Изберете езика си**","select_prompt":"Изберете езика, който искате да използвате за съобщенията на AniToon Bot.","confirm":"✅ Потвърди","language_saved":"✅ Езикът е запазен успешно.","settings_language":"🌐 Език","settings_title":"⚙️ **Настройки на AniToon**","settings_choose":"Изберете какво искате да управлявате:","back":"🔙 Назад","language_changed":"✅ Езикът е променен успешно."},
    "zh": {"select_title":"🌐 **选择您的语言**","select_prompt":"选择您希望用于 AniToon Bot 消息的语言。","confirm":"✅ 确认","language_saved":"✅ 语言已成功保存。","settings_language":"🌐 语言","settings_title":"⚙️ **AniToon 设置**","settings_choose":"选择您要管理的项目：","back":"🔙 返回","language_changed":"✅ 语言已成功更改。"},
    "hr": {"select_title":"🌐 **Odaberite svoj jezik**","select_prompt":"Odaberite jezik koji želite koristiti za poruke AniToon Bota.","confirm":"✅ Potvrdi","language_saved":"✅ Jezik je uspješno spremljen.","settings_language":"🌐 Jezik","settings_title":"⚙️ **AniToon postavke**","settings_choose":"Odaberite čime želite upravljati:","back":"🔙 Natrag","language_changed":"✅ Jezik je uspješno promijenjen."},
    "cs": {"select_title":"🌐 **Vyberte svůj jazyk**","select_prompt":"Vyberte jazyk, který chcete používat pro zprávy AniToon Bota.","confirm":"✅ Potvrdit","language_saved":"✅ Jazyk byl úspěšně uložen.","settings_language":"🌐 Jazyk","settings_title":"⚙️ **Nastavení AniToon**","settings_choose":"Vyberte, co chcete spravovat:","back":"🔙 Zpět","language_changed":"✅ Jazyk byl úspěšně změněn."},
    "da": {"select_title":"🌐 **Vælg dit sprog**","select_prompt":"Vælg det sprog, du vil bruge til AniToon Bots beskeder.","confirm":"✅ Bekræft","language_saved":"✅ Sproget er gemt.","settings_language":"🌐 Sprog","settings_title":"⚙️ **AniToon Indstillinger**","settings_choose":"Vælg, hvad du vil administrere:","back":"🔙 Tilbage","language_changed":"✅ Sproget er ændret."},
    "nl": {"select_title":"🌐 **Kies je taal**","select_prompt":"Kies de taal die je wilt gebruiken voor berichten van AniToon Bot.","confirm":"✅ Bevestigen","language_saved":"✅ Taal succesvol opgeslagen.","settings_language":"🌐 Taal","settings_title":"⚙️ **AniToon Instellingen**","settings_choose":"Kies wat je wilt beheren:","back":"🔙 Terug","language_changed":"✅ Taal succesvol gewijzigd."},
    "fi": {"select_title":"🌐 **Valitse kielesi**","select_prompt":"Valitse kieli, jota haluat käyttää AniToon Botin viesteissä.","confirm":"✅ Vahvista","language_saved":"✅ Kieli tallennettiin onnistuneesti.","settings_language":"🌐 Kieli","settings_title":"⚙️ **AniToon Asetukset**","settings_choose":"Valitse, mitä haluat hallita:","back":"🔙 Takaisin","language_changed":"✅ Kieli vaihdettiin onnistuneesti."},
    "fr": {"select_title":"🌐 **Choisissez votre langue**","select_prompt":"Choisissez la langue que vous souhaitez utiliser pour les messages du bot AniToon.","confirm":"✅ Confirmer","language_saved":"✅ Langue enregistrée avec succès.","settings_language":"🌐 Langue","settings_title":"⚙️ **Paramètres AniToon**","settings_choose":"Choisissez ce que vous souhaitez gérer :","back":"🔙 Retour","language_changed":"✅ Langue modifiée avec succès."},
    "ka": {"select_title":"🌐 **აირჩიეთ თქვენი ენა**","select_prompt":"აირჩიეთ ენა, რომელიც გსურთ გამოიყენოთ AniToon Bot-ის შეტყობინებებისთვის.","confirm":"✅ დადასტურება","language_saved":"✅ ენა წარმატებით შეინახა.","settings_language":"🌐 ენა","settings_title":"⚙️ **AniToon-ის პარამეტრები**","settings_choose":"აირჩიეთ, რისი მართვა გსურთ:","back":"🔙 უკან","language_changed":"✅ ენა წარმატებით შეიცვალა."},
    "de": {"select_title":"🌐 **Wählen Sie Ihre Sprache**","select_prompt":"Wählen Sie die Sprache, die Sie für AniToon-Bot-Nachrichten verwenden möchten.","confirm":"✅ Bestätigen","language_saved":"✅ Sprache erfolgreich gespeichert.","settings_language":"🌐 Sprache","settings_title":"⚙️ **AniToon Einstellungen**","settings_choose":"Wählen Sie, was Sie verwalten möchten:","back":"🔙 Zurück","language_changed":"✅ Sprache erfolgreich geändert."},
    "el": {"select_title":"🌐 **Επιλέξτε τη γλώσσα σας**","select_prompt":"Επιλέξτε τη γλώσσα που θέλετε να χρησιμοποιείτε για τα μηνύματα του AniToon Bot.","confirm":"✅ Επιβεβαίωση","language_saved":"✅ Η γλώσσα αποθηκεύτηκε με επιτυχία.","settings_language":"🌐 Γλώσσα","settings_title":"⚙️ **Ρυθμίσεις AniToon**","settings_choose":"Επιλέξτε τι θέλετε να διαχειριστείτε:","back":"🔙 Πίσω","language_changed":"✅ Η γλώσσα άλλαξε με επιτυχία."},
    "he": {"select_title":"🌐 **בחרו את השפה שלכם**","select_prompt":"בחרו את השפה שבה תרצו להשתמש להודעות AniToon Bot.","confirm":"✅ אישור","language_saved":"✅ השפה נשמרה בהצלחה.","settings_language":"🌐 שפה","settings_title":"⚙️ **הגדרות AniToon**","settings_choose":"בחרו מה ברצונכם לנהל:","back":"🔙 חזרה","language_changed":"✅ השפה שונתה בהצלחה."},
    "hi": {"select_title":"🌐 **अपनी भाषा चुनें**","select_prompt":"AniToon Bot के संदेशों के लिए आप जिस भाषा का उपयोग करना चाहते हैं उसे चुनें।","confirm":"✅ पुष्टि करें","language_saved":"✅ भाषा सफलतापूर्वक सहेजी गई।","settings_language":"🌐 भाषा","settings_title":"⚙️ **AniToon सेटिंग्स**","settings_choose":"आप क्या प्रबंधित करना चाहते हैं चुनें:","back":"🔙 वापस","language_changed":"✅ भाषा सफलतापूर्वक बदल दी गई।"},
    "hu": {"select_title":"🌐 **Válassza ki a nyelvét**","select_prompt":"Válassza ki az AniToon Bot üzeneteihez használni kívánt nyelvet.","confirm":"✅ Megerősítés","language_saved":"✅ A nyelv sikeresen mentve.","settings_language":"🌐 Nyelv","settings_title":"⚙️ **AniToon Beállítások**","settings_choose":"Válassza ki, mit szeretne kezelni:","back":"🔙 Vissza","language_changed":"✅ A nyelv sikeresen megváltozott."},
    "id": {"select_title":"🌐 **Pilih Bahasa Anda**","select_prompt":"Pilih bahasa yang ingin Anda gunakan untuk pesan AniToon Bot.","confirm":"✅ Konfirmasi","language_saved":"✅ Bahasa berhasil disimpan.","settings_language":"🌐 Bahasa","settings_title":"⚙️ **Pengaturan AniToon**","settings_choose":"Pilih yang ingin Anda kelola:","back":"🔙 Kembali","language_changed":"✅ Bahasa berhasil diubah."},
    "it": {"select_title":"🌐 **Seleziona la tua lingua**","select_prompt":"Scegli la lingua che vuoi usare per i messaggi di AniToon Bot.","confirm":"✅ Conferma","language_saved":"✅ Lingua salvata con successo.","settings_language":"🌐 Lingua","settings_title":"⚙️ **Impostazioni AniToon**","settings_choose":"Scegli cosa vuoi gestire:","back":"🔙 Indietro","language_changed":"✅ Lingua modificata con successo."},
    "ja": {"select_title":"🌐 **言語を選択してください**","select_prompt":"AniToon Bot のメッセージで使用する言語を選択してください。","confirm":"✅ 確認","language_saved":"✅ 言語を保存しました。","settings_language":"🌐 言語","settings_title":"⚙️ **AniToon 設定**","settings_choose":"管理する項目を選択してください：","back":"🔙 戻る","language_changed":"✅ 言語を変更しました。"},
    "kk": {"select_title":"🌐 **Тіліңізді таңдаңыз**","select_prompt":"AniToon Bot хабарламалары үшін пайдаланғыңыз келетін тілді таңдаңыз.","confirm":"✅ Растау","language_saved":"✅ Тіл сәтті сақталды.","settings_language":"🌐 Тіл","settings_title":"⚙️ **AniToon Баптаулары**","settings_choose":"Басқарғыңыз келетін бөлімді таңдаңыз:","back":"🔙 Артқа","language_changed":"✅ Тіл сәтті өзгертілді."},
    "ko": {"select_title":"🌐 **언어를 선택하세요**","select_prompt":"AniToon Bot 메시지에 사용할 언어를 선택하세요.","confirm":"✅ 확인","language_saved":"✅ 언어가 성공적으로 저장되었습니다.","settings_language":"🌐 언어","settings_title":"⚙️ **AniToon 설정**","settings_choose":"관리할 항목을 선택하세요:","back":"🔙 뒤로","language_changed":"✅ 언어가 성공적으로 변경되었습니다."},
    "ms": {"select_title":"🌐 **Pilih Bahasa Anda**","select_prompt":"Pilih bahasa yang anda mahu gunakan untuk mesej AniToon Bot.","confirm":"✅ Sahkan","language_saved":"✅ Bahasa berjaya disimpan.","settings_language":"🌐 Bahasa","settings_title":"⚙️ **Tetapan AniToon**","settings_choose":"Pilih perkara yang anda mahu uruskan:","back":"🔙 Kembali","language_changed":"✅ Bahasa berjaya ditukar."},
    "ml": {"select_title":"🌐 **നിങ്ങളുടെ ഭാഷ തിരഞ്ഞെടുക്കുക**","select_prompt":"AniToon Bot സന്ദേശങ്ങൾക്ക് ഉപയോഗിക്കേണ്ട ഭാഷ തിരഞ്ഞെടുക്കുക.","confirm":"✅ സ്ഥിരീകരിക്കുക","language_saved":"✅ ഭാഷ വിജയകരമായി സംരക്ഷിച്ചു.","settings_language":"🌐 ഭാഷ","settings_title":"⚙️ **AniToon ക്രമീകരണങ്ങൾ**","settings_choose":"നിങ്ങൾ നിയന്ത്രിക്കേണ്ടത് തിരഞ്ഞെടുക്കുക:","back":"🔙 മടങ്ങുക","language_changed":"✅ ഭാഷ വിജയകരമായി മാറ്റി."},
    "mr": {"select_title":"🌐 **तुमची भाषा निवडा**","select_prompt":"AniToon Bot संदेशांसाठी वापरायची भाषा निवडा.","confirm":"✅ पुष्टी करा","language_saved":"✅ भाषा यशस्वीरित्या जतन केली.","settings_language":"🌐 भाषा","settings_title":"⚙️ **AniToon सेटिंग्ज**","settings_choose":"तुम्हाला काय व्यवस्थापित करायचे आहे ते निवडा:","back":"🔙 मागे","language_changed":"✅ भाषा यशस्वीरित्या बदलली."},
    "ne": {"select_title":"🌐 **आफ्नो भाषा छान्नुहोस्**","select_prompt":"AniToon Bot का सन्देशहरूका लागि प्रयोग गर्न चाहनुभएको भाषा छान्नुहोस्।","confirm":"✅ पुष्टि गर्नुहोस्","language_saved":"✅ भाषा सफलतापूर्वक सुरक्षित भयो।","settings_language":"🌐 भाषा","settings_title":"⚙️ **AniToon सेटिङहरू**","settings_choose":"तपाईं के व्यवस्थापन गर्न चाहनुहुन्छ छान्नुहोस्:","back":"🔙 पछाडि","language_changed":"✅ भाषा सफलतापूर्वक परिवर्तन भयो।"},
    "no": {"select_title":"🌐 **Velg språket ditt**","select_prompt":"Velg språket du vil bruke for AniToon Bot-meldinger.","confirm":"✅ Bekreft","language_saved":"✅ Språket er lagret.","settings_language":"🌐 Språk","settings_title":"⚙️ **AniToon Innstillinger**","settings_choose":"Velg hva du vil administrere:","back":"🔙 Tilbake","language_changed":"✅ Språket er endret."},
    "or": {"select_title":"🌐 **ଆପଣଙ୍କ ଭାଷା ବାଛନ୍ତୁ**","select_prompt":"AniToon Bot ବାର୍ତ୍ତା ପାଇଁ ଆପଣ ବ୍ୟବହାର କରିବାକୁ ଚାହୁଁଥିବା ଭାଷା ବାଛନ୍ତୁ।","confirm":"✅ ନିଶ୍ଚିତ କରନ୍ତୁ","language_saved":"✅ ଭାଷା ସଫଳତାର ସହ ସଞ୍ଚୟ ହେଲା।","settings_language":"🌐 ଭାଷା","settings_title":"⚙️ **AniToon ସେଟିଂସ୍**","settings_choose":"ଆପଣ କଣ ପରିଚାଳନା କରିବାକୁ ଚାହୁଁଛନ୍ତି ବାଛନ୍ତୁ:","back":"🔙 ପଛକୁ","language_changed":"✅ ଭାଷା ସଫଳତାର ସହ ପରିବର୍ତ୍ତିତ ହେଲା।"},
    "fa": {"select_title":"🌐 **زبان خود را انتخاب کنید**","select_prompt":"زبانی را که می‌خواهید برای پیام‌های ربات AniToon استفاده کنید انتخاب کنید.","confirm":"✅ تأیید","language_saved":"✅ زبان با موفقیت ذخیره شد.","settings_language":"🌐 زبان","settings_title":"⚙️ **تنظیمات AniToon**","settings_choose":"آنچه را می‌خواهید مدیریت کنید انتخاب کنید:","back":"🔙 بازگشت","language_changed":"✅ زبان با موفقیت تغییر کرد."},
    "fil": {"select_title":"🌐 **Piliin ang Iyong Wika**","select_prompt":"Piliin ang wikang gusto mong gamitin para sa mga mensahe ng AniToon Bot.","confirm":"✅ Kumpirmahin","language_saved":"✅ Matagumpay na na-save ang wika.","settings_language":"🌐 Wika","settings_title":"⚙️ **Mga Setting ng AniToon**","settings_choose":"Piliin kung ano ang gusto mong pamahalaan:","back":"🔙 Bumalik","language_changed":"✅ Matagumpay na nabago ang wika."},
    "pl": {"select_title":"🌐 **Wybierz swój język**","select_prompt":"Wybierz język, którego chcesz używać dla wiadomości AniToon Bot.","confirm":"✅ Potwierdź","language_saved":"✅ Język został zapisany.","settings_language":"🌐 Język","settings_title":"⚙️ **Ustawienia AniToon**","settings_choose":"Wybierz, czym chcesz zarządzać:","back":"🔙 Wstecz","language_changed":"✅ Język został zmieniony."},
    "pt": {"select_title":"🌐 **Selecione seu idioma**","select_prompt":"Escolha o idioma que deseja usar nas mensagens do AniToon Bot.","confirm":"✅ Confirmar","language_saved":"✅ Idioma salvo com sucesso.","settings_language":"🌐 Idioma","settings_title":"⚙️ **Configurações do AniToon**","settings_choose":"Escolha o que deseja gerenciar:","back":"🔙 Voltar","language_changed":"✅ Idioma alterado com sucesso."},
    "pa": {"select_title":"🌐 **ਆਪਣੀ ਭਾਸ਼ਾ ਚੁਣੋ**","select_prompt":"AniToon Bot ਦੇ ਸੁਨੇਹਿਆਂ ਲਈ ਵਰਤਣ ਵਾਲੀ ਭਾਸ਼ਾ ਚੁਣੋ।","confirm":"✅ ਪੁਸ਼ਟੀ ਕਰੋ","language_saved":"✅ ਭਾਸ਼ਾ ਸਫਲਤਾਪੂਰਵਕ ਸੇਵ ਹੋ ਗਈ।","settings_language":"🌐 ਭਾਸ਼ਾ","settings_title":"⚙️ **AniToon ਸੈਟਿੰਗਾਂ**","settings_choose":"ਤੁਸੀਂ ਕੀ ਪ੍ਰਬੰਧਿਤ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ ਚੁਣੋ:","back":"🔙 ਵਾਪਸ","language_changed":"✅ ਭਾਸ਼ਾ ਸਫਲਤਾਪੂਰਵਕ ਬਦਲੀ ਗਈ।"},
    "ro": {"select_title":"🌐 **Alegeți limba**","select_prompt":"Alegeți limba pe care doriți să o utilizați pentru mesajele AniToon Bot.","confirm":"✅ Confirmă","language_saved":"✅ Limba a fost salvată cu succes.","settings_language":"🌐 Limbă","settings_title":"⚙️ **Setări AniToon**","settings_choose":"Alegeți ce doriți să gestionați:","back":"🔙 Înapoi","language_changed":"✅ Limba a fost schimbată cu succes."},
    "ru": {"select_title":"🌐 **Выберите язык**","select_prompt":"Выберите язык, который хотите использовать для сообщений AniToon Bot.","confirm":"✅ Подтвердить","language_saved":"✅ Язык успешно сохранён.","settings_language":"🌐 Язык","settings_title":"⚙️ **Настройки AniToon**","settings_choose":"Выберите, чем хотите управлять:","back":"🔙 Назад","language_changed":"✅ Язык успешно изменён."},
    "sr": {"select_title":"🌐 **Изаберите језик**","select_prompt":"Изаберите језик који желите да користите за поруке AniToon бота.","confirm":"✅ Потврди","language_saved":"✅ Језик је успешно сачуван.","settings_language":"🌐 Језик","settings_title":"⚙️ **AniToon подешавања**","settings_choose":"Изаберите шта желите да управљате:","back":"🔙 Назад","language_changed":"✅ Језик је успешно промењен."},
    "sk": {"select_title":"🌐 **Vyberte svoj jazyk**","select_prompt":"Vyberte jazyk, ktorý chcete používať pre správy AniToon Bota.","confirm":"✅ Potvrdiť","language_saved":"✅ Jazyk bol úspešne uložený.","settings_language":"🌐 Jazyk","settings_title":"⚙️ **Nastavenia AniToon**","settings_choose":"Vyberte, čo chcete spravovať:","back":"🔙 Späť","language_changed":"✅ Jazyk bol úspešne zmenený."},
    "sl": {"select_title":"🌐 **Izberite svoj jezik**","select_prompt":"Izberite jezik, ki ga želite uporabljati za sporočila AniToon Bota.","confirm":"✅ Potrdi","language_saved":"✅ Jezik je bil uspešno shranjen.","settings_language":"🌐 Jezik","settings_title":"⚙️ **Nastavitve AniToon**","settings_choose":"Izberite, kaj želite upravljati:","back":"🔙 Nazaj","language_changed":"✅ Jezik je bil uspešno spremenjen."},
    "es": {"select_title":"🌐 **Selecciona tu idioma**","select_prompt":"Elige el idioma que quieres usar para los mensajes de AniToon Bot.","confirm":"✅ Confirmar","language_saved":"✅ Idioma guardado correctamente.","settings_language":"🌐 Idioma","settings_title":"⚙️ **Ajustes de AniToon**","settings_choose":"Elige lo que quieres administrar:","back":"🔙 Atrás","language_changed":"✅ Idioma cambiado correctamente."},
    "si": {"select_title":"🌐 **ඔබගේ භාෂාව තෝරන්න**","select_prompt":"AniToon Bot පණිවිඩ සඳහා භාවිතා කිරීමට අවශ්‍ය භාෂාව තෝරන්න.","confirm":"✅ තහවුරු කරන්න","language_saved":"✅ භාෂාව සාර්ථකව සුරකින ලදී.","settings_language":"🌐 භාෂාව","settings_title":"⚙️ **AniToon සැකසුම්**","settings_choose":"ඔබට කළමනාකරණය කිරීමට අවශ්‍ය දේ තෝරන්න:","back":"🔙 ආපසු","language_changed":"✅ භාෂාව සාර්ථකව වෙනස් කරන ලදී."},
    "sv": {"select_title":"🌐 **Välj ditt språk**","select_prompt":"Välj språket du vill använda för AniToon Bots meddelanden.","confirm":"✅ Bekräfta","language_saved":"✅ Språket har sparats.","settings_language":"🌐 Språk","settings_title":"⚙️ **AniToon Inställningar**","settings_choose":"Välj vad du vill hantera:","back":"🔙 Tillbaka","language_changed":"✅ Språket har ändrats."},
    "th": {"select_title":"🌐 **เลือกภาษาของคุณ**","select_prompt":"เลือกภาษาที่ต้องการใช้สำหรับข้อความของ AniToon Bot","confirm":"✅ ยืนยัน","language_saved":"✅ บันทึกภาษาเรียบร้อยแล้ว","settings_language":"🌐 ภาษา","settings_title":"⚙️ **การตั้งค่า AniToon**","settings_choose":"เลือกสิ่งที่คุณต้องการจัดการ:","back":"🔙 กลับ","language_changed":"✅ เปลี่ยนภาษาเรียบร้อยแล้ว"},
    "ta": {"select_title":"🌐 **உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்**","select_prompt":"AniToon Bot செய்திகளுக்கு நீங்கள் பயன்படுத்த விரும்பும் மொழியைத் தேர்ந்தெடுக்கவும்.","confirm":"✅ உறுதிப்படுத்து","language_saved":"✅ மொழி வெற்றிகரமாக சேமிக்கப்பட்டது.","settings_language":"🌐 மொழி","settings_title":"⚙️ **AniToon அமைப்புகள்**","settings_choose":"நீங்கள் நிர்வகிக்க விரும்புவதைத் தேர்ந்தெடுக்கவும்:","back":"🔙 பின்செல்","language_changed":"✅ மொழி வெற்றிகரமாக மாற்றப்பட்டது."},
    "te": {"select_title":"🌐 **మీ భాషను ఎంచుకోండి**","select_prompt":"AniToon Bot సందేశాల కోసం మీరు ఉపయోగించాలనుకునే భాషను ఎంచుకోండి.","confirm":"✅ నిర్ధారించండి","language_saved":"✅ భాష విజయవంతంగా సేవ్ చేయబడింది.","settings_language":"🌐 భాష","settings_title":"⚙️ **AniToon సెట్టింగ్స్**","settings_choose":"మీరు నిర్వహించాలనుకునే దాన్ని ఎంచుకోండి:","back":"🔙 వెనక్కి","language_changed":"✅ భాష విజయవంతంగా మార్చబడింది."},
    "tr": {"select_title":"🌐 **Dilinizi Seçin**","select_prompt":"AniToon Bot mesajları için kullanmak istediğiniz dili seçin.","confirm":"✅ Onayla","language_saved":"✅ Dil başarıyla kaydedildi.","settings_language":"🌐 Dil","settings_title":"⚙️ **AniToon Ayarları**","settings_choose":"Yönetmek istediğiniz şeyi seçin:","back":"🔙 Geri","language_changed":"✅ Dil başarıyla değiştirildi."},
    "uk": {"select_title":"🌐 **Оберіть мову**","select_prompt":"Оберіть мову, яку хочете використовувати для повідомлень AniToon Bot.","confirm":"✅ Підтвердити","language_saved":"✅ Мову успішно збережено.","settings_language":"🌐 Мова","settings_title":"⚙️ **Налаштування AniToon**","settings_choose":"Оберіть, чим хочете керувати:","back":"🔙 Назад","language_changed":"✅ Мову успішно змінено."},
    "ur": {"select_title":"🌐 **اپنی زبان منتخب کریں**","select_prompt":"AniToon Bot کے پیغامات کے لیے وہ زبان منتخب کریں جو آپ استعمال کرنا چاہتے ہیں۔","confirm":"✅ تصدیق کریں","language_saved":"✅ زبان کامیابی سے محفوظ ہو گئی۔","settings_language":"🌐 زبان","settings_title":"⚙️ **AniToon ترتیبات**","settings_choose":"منتظم کرنے کے لیے چیز منتخب کریں:","back":"🔙 واپس","language_changed":"✅ زبان کامیابی سے تبدیل ہو گئی۔"},
    "uz": {"select_title":"🌐 **Tilingizni tanlang**","select_prompt":"AniToon Bot xabarlari uchun foydalanmoqchi bo‘lgan tilni tanlang.","confirm":"✅ Tasdiqlash","language_saved":"✅ Til muvaffaqiyatli saqlandi.","settings_language":"🌐 Til","settings_title":"⚙️ **AniToon Sozlamalari**","settings_choose":"Boshqarmoqchi bo‘lgan bo‘limni tanlang:","back":"🔙 Orqaga","language_changed":"✅ Til muvaffaqiyatli o‘zgartirildi."},
    "vi": {"select_title":"🌐 **Chọn ngôn ngữ của bạn**","select_prompt":"Chọn ngôn ngữ bạn muốn sử dụng cho tin nhắn của AniToon Bot.","confirm":"✅ Xác nhận","language_saved":"✅ Ngôn ngữ đã được lưu thành công.","settings_language":"🌐 Ngôn ngữ","settings_title":"⚙️ **Cài đặt AniToon**","settings_choose":"Chọn nội dung bạn muốn quản lý:","back":"🔙 Quay lại","language_changed":"✅ Ngôn ngữ đã được thay đổi thành công."},
}


def is_valid_language(code: str | None) -> bool:
    return str(code or "").lower() in _LANGUAGE_MAP


def language_info(code: str | None) -> dict:
    return _LANGUAGE_MAP.get(str(code or DEFAULT_LANGUAGE).lower(), _LANGUAGE_MAP[DEFAULT_LANGUAGE])


def t(lang: str | None, key: str) -> str:
    code = str(lang or DEFAULT_LANGUAGE).lower()
    return _TRANSLATIONS.get(code, _TRANSLATIONS[DEFAULT_LANGUAGE]).get(
        key,
        _TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key),
    )


def language_label(code: str | None) -> str:
    info = language_info(code)
    return f"{info['flag']} {info['name']}"


# Runtime localization cache and helpers.
_LANGUAGE_CACHE: dict[int, str] = {}


def remember_language(user_id: int, language: str | None) -> None:
    value = str(language or "").strip().lower()
    if value and is_valid_language(value):
        _LANGUAGE_CACHE[int(user_id)] = value
    else:
        _LANGUAGE_CACHE.pop(int(user_id), None)


async def user_language(user_id: int) -> str:
    uid = int(user_id)
    cached = _LANGUAGE_CACHE.get(uid)
    if cached:
        return cached
    try:
        from helper.database import db
        value = await db.get_language(uid)
    except Exception:
        value = None
    language = value if is_valid_language(value) else DEFAULT_LANGUAGE
    _LANGUAGE_CACHE[uid] = language
    return language


def localize_text(lang: str | None, text):
    """Translate known bot UI phrases while preserving filenames, user input and values."""
    if not isinstance(text, str) or not text:
        return text
    code = str(lang or DEFAULT_LANGUAGE).lower()
    if not is_valid_language(code) or code == DEFAULT_LANGUAGE:
        return text

    try:
        from language.strings import STRINGS, EXTENDED_STRINGS
        catalog = {}
        catalog.update(STRINGS.get(code, {}))
        catalog.update(EXTENDED_STRINGS.get(code, {}))
        # Longest phrases first prevents partial replacements from corrupting
        # larger translated sentences.
        for source in sorted(catalog, key=len, reverse=True):
            target = catalog.get(source)
            if not source or not target or source == target:
                continue
            text = text.replace(source, target)
    except Exception:
        pass
    return text
