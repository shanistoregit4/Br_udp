# ⚡ FreeFire Level Up Bot (Auto Farming Engine)

यह एक हाई-स्पीड ऑटोमैटिक Free Fire लेवल-अप फार्मिंग टूल है। यह सीधे गेम के TCP/UDP गेटवे से हैंडशेक करता है, लाइव इन-गेम सर्वाइवल ट्रैक करता है और बिना गेम ओपन किए आपके अकाउंट्स का लेवल तेज़ी से बढ़ाता है[span_0](start_span)[span_0](end_span)[span_1](start_span)[span_1](end_span)।

---

## 📁 1. प्रोजेक्ट डायरेक्टरी स्ट्रक्चर (Project Structure)

स्क्रिप्ट सही तरीके से चलने के लिए आपके मुख्य फ़ोल्डर में निम्नलिखित सभी फ़ाइलें होना अनिवार्य है[span_2](start_span)[span_2](end_span)[span_3](start_span)[span_3](end_span):

```text
├── krll.py (या app.py)      # मुख्य बॉट स्क्रिप्ट (Main Runner File)
├── thunderFF_pb2.py        # प्रोटोबफ़ डिकोडर और एनकोडर फ़ाइल
├── message_ids.py          # इन-गेम UDP/RUDP पैकेट आईडी मैपिंग फ़ाइल
├── accounts.json           # अकाउंट्स का लॉगिन डेटा
├── proxies.txt             # SOCKS5 प्रॉक्सी लिस्ट (वैकल्पिक / Optional)
├── requirements.txt        # आवश्यक पायथन पैकेज की लिस्ट
└── README.md               # यह गाइड / डॉक्यूमेंटेशन फ़ाइल



## Local dashboard

Run `python krll3.py`, then open `http://127.0.0.1:20335` on the same device. The dashboard lets you add, refresh, and remove UID/password accounts. Only accounts saved through the dashboard (stored in `accounts.json`) are started; the built-in fallback account has been removed. Keep `accounts.json` private because it contains credentials.
