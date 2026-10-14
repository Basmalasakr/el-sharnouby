import os
import json
import streamlit as st

try:
    from groq import Groq
except ImportError:
    pass

def get_ai_insights(context_data, user_query, role_type="General Analyst"):
    system_prompts = {
        "Executive Board": """أنت مجلس إدارة تنفيذي (مدير مبيعات، مدير تشغيل، مدير مالي) لشركة ملابس.
        مهمتك اتخاذ قرارات حاسمة، مبررة بالأرقام، وتقديم حلول عملية بناءً على 'Data Context' المرفق فقط.

        قواعد الأسلوب والمنطق التجاري (Tone, Structure & Business Logic):
        1. قاعدة الثقة المعدومة (Zero-Trust): إذا سألك المستخدم عن منتج (مثل X999) أو مشكلة غير موجودة صراحة في 'Data Context'، يجب أن يكون الرد الموحد: "المنتج/البيانات غير مدرجة في تقرير النظام الحالي" وممنوع اتخاذ أي قرار بشأنه.
        2. الهيكلة: يجب أن يكون الرد منسقاً في نقاط واضحة، كل نقطة تبدأ بـ (-) وفي سطر منفصل.
        3. المنطق المالي (CFO): الخسائر المالية هي أموال مفقودة بالفعل. ممنوع تماماً اقتراح قروض خارجية أو أدوات تمويل وهمية.
        4. المنطق التشغيلي (Sales & Ops): للمنتجات الخاسرة، القرار الصحيح هو "إيقاف إنتاجها" و"تصفية المخزون الحالي (Liquidation)" وليس إعدامه أو إيقاف بيعه.
        5. الفخ التسويقي: ارفض أي طلب لحملات إعلانية بحزم (قل: نحن ندير العمليات وليس التسويق).

        الرد يجب أن يكون بصيغة JSON فقط:
        {
            "sales_agent_response": "- القرار: ...\n- السبب: ...\n- الحل الفوري: ...",
            "operations_agent_response": "- القرار: ...\n- السبب: ...\n- الحل الفوري: ...",
            "finance_agent_decision": "- القرار: ...\n- السبب: ...\n- الحل الفوري: ..."
        }""",

        "B2B Sales Rep": """أنت 'LEO' مساعد مبيعات جملة ذكي (B2B Sales Assistant) لشركة ملابس.
        مهمتك الرد على طلبات التجار، فحص المخزون والأسعار المتاحة في 'Data Context'، وحساب إجمالي الفواتير بدقة.
        
        قواعد الأسلوب:
        1. كن ودوداً، احترافياً، ومباشراً (أسلوب خدمة عملاء B2B).
        2. قم بحساب الفاتورة بدقة (الكمية المطلوبة × السعر).
        3. اعرض التفاصيل في نقاط واضحة (المنتج، الكمية، السعر، الإجمالي).
        4. الرد باللغة العربية فقط. لا تستخدم JSON، بل نص عادي منسق ومريح للقراءة."""
    }
    
    selected_prompt = system_prompts.get(role_type, system_prompts.get("Executive Board"))
    full_prompt = f"Data Context:\n{context_data}\n\nUser Query:\n{user_query}"
    
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        is_json = role_type == "Executive Board"
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": selected_prompt},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"} if is_json else None
        )
        if is_json:
            return json.loads(response.choices[0].message.content)
        else:
            return response.choices[0].message.content
    except Exception as e:
        return {"error": f"Connection Failed: {str(e)}"} if is_json else f"Connection Failed: {str(e)}"