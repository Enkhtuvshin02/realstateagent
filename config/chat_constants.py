MESSAGE_TYPES = {
    "PROPERTY_URL": "property_url",
    "DISTRICT_QUERY": "district_query",
    "MARKET_RESEARCH": "market_research",
    "REPORT_REQUEST": "report_request",
    "GENERAL": "general"
}


REPORT_ACCEPTANCE_KEYWORDS = [
    'Тийм', 'тийм', 'yes', 'тайлан хүсэж байна',
    'хүсэж байна', 'гаргана уу', 'үүсгэнэ үү'
]


DISTRICT_NAMES = [
    "хан-уул", "баянгол", "сүхбаатар", "чингэлтэй",
    "баянзүрх", "сонгинохайрхан", "багануур", "налайх", "багахангай"
]


CLASSIFICATION_KEYWORDS = {
    "report": [
        'тайлан', 'report', 'pdf', 'татаж авах', 'download',
        'тайлан үүсгэх', 'generate report'
    ],
    "location": [
        "дүүрэг", "байршил", "хот", "газар", "орон сууц", "байр"
    ],
    "comparison": [
        "бүх дүүрэг", "дүүрэг харьцуулах", "дүүргүүд", "харьцуулалт",
        "compare", "all districts", "дүүргийн үнэ", "үнэ харьцуулах"
    ],
    "market": [
        "зах зээл", "үнийн чиглэл", "market", "тренд", "статистик",
        "хөрөнгө оруулалт", "investment", "зээл", "ипотек"
    ]
}


COT_INDICATORS = {
    "complex_terms": [
        'дэлгэрэнгүй', 'шинжилгээ', 'хөрөнгө оруулалт', 'харьцуулах',
        'зөвлөмж', 'investment', 'analysis', 'compare', 'detailed'
    ],
    "always_apply_types": ['property_url', 'district_query', 'market_research'],
    "min_message_length": 50,
    "complex_response_length": 150
}


REPORT_TYPES = {
    "PROPERTY": "property",
    "DISTRICT": "district",
    "COMPREHENSIVE": "comprehensive"
}


REPORT_TYPE_KEYWORDS = {
    "district": ['дүүргийн тайлан', 'дүүрэг харьцуулах', 'бүх дүүрэг'],
    "comprehensive": ['иж бүрэн', 'дэлгэрэнгүй зах зээл', 'зах зээлийн тайлан']
}


RESPONSE_TEMPLATES = {
    "property_offer": "\n\n**Тайлан авах уу?**\nЭнэ орон сууцны дэлгэрэнгүй PDF тайлан авахыг хүсвэл Тийм гэж бичнэ үү.",
    "district_offer": "\n\n**Тайлан авах уу?**\nДүүргийн харьцуулалтын PDF тайлан авахыг хүсвэл Тийм гэж бичнэ үү.",
    "market_offer": "\n\n**Тайлан авах уу?**\nЗах зээлийн дэлгэрэнгүй PDF тайлан авахыг хүсвэл Тийм гэж бичнэ үү.",
    "general_offer": "\n\n**Тайлан авах уу?**\nЭнэ мэдээллийн PDF тайлан авахыг хүсвэл Тийм гэж бичнэ үү."
}


ERROR_MESSAGES = {
    "general_error": "Уучлаарай, алдаа гарлаа. Дахин оролдоно уу.",
    "url_not_found": "URL олдсонгүй.",
    "property_extraction_failed": "Мэдээлэл татаж авахад алдаа гарлаа: {}",
    "property_url_error": "URL боловсруулахад алдаа гарлаа: {}",
    "district_processing_error": "Дүүргийн мэдээлэл боловсруулахад алдаа гарлаа. Дахин оролдоно уу.",
    "market_research_error": "Зах зээлийн судалгаа хийхэд алдаа гарлаа.",
    "search_error": "Хайлт хийхэд алдаа гарлаа. Дахин оролдоно уу.",
    "report_generation_error": "Тайлан үүсгэхэд алдаа гарлаа: {}",
    "no_property_data": "Орон сууцны мэдээлэл байхгүй. Эхлээд орон сууцны холбоос илгээнэ үү.",
    "unknown_report_type": "Тайлангийн төрөл тодорхойгүй байна."
}


SYSTEM_PROMPTS = {
    "property_analysis": "You are a professional real estate expert. Analyze this property and provide valuable insights.\n\nFocus on:\n1. Price evaluation - is it fair value?\n2. Location benefits and drawbacks  \n3. Investment potential with numbers\n4. Key recommendations\n\nBe specific, use numbers, and provide actionable advice.\n\nIMPORTANT: Respond ONLY in Mongolian language.",
    "district_analysis": "You are a real estate market analyst. Provide clear district analysis with specific insights.\n\nFocus on:\n1. Current price levels with numbers\n2. Comparison to other districts\n3. Investment opportunities \n4. Who should buy here\n5. Future outlook\n\nBe specific and provide actionable recommendations.\n\nIMPORTANT: Respond ONLY in Mongolian language.",
    "market_research": "You are a real estate market researcher. Analyze search results and provide valuable market insights.\n\nFocus on:\n1. Current market conditions\n2. Price trends with specifics\n3. Investment opportunities\n4. Risks to watch\n5. Actionable recommendations\n\nBe specific with data and provide clear guidance.\n\nIMPORTANT: Respond ONLY in Mongolian language.",
    "general_query": "You are a professional real estate assistant specializing in Mongolia's property market. Provide clear, helpful answers based on search results.\n\nProvide:\n- Direct answer to the user's question\n- Relevant facts and data\n- Practical advice if applicable\n- Clear, actionable information\n\nIMPORTANT: Respond ONLY in Mongolian language with clear, valuable information."
}


CONFIG = {
    "max_acceptance_message_length": 50,
    "min_complex_response_length": 200,
    "cot_approach": "selective_application"
}


SPECIAL_FLAGS = {
    "all_districts_comparison": "ALL_DISTRICTS_COMPARISON"
}