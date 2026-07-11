import pandas as pd

# Define the data
data = [
    ["Категория", "Параметр", "Значение", "Ед. изм.", "Описание"],
    ["Инфраструктура", "Серверы и БД (Фикс)", 65, "$/мес", "Общие затраты на сервера ($40) + Supabase ($25)"],
    ["Общие Инструменты", "Master Sales Navigator", 99, "$/мес", "Стоимость 1 премиум аккаунта Sales Nav (для общих тарифов)"],
    ["Общие Инструменты", "Лимит аккаунта Sales Nav", 2000, "кандидатов/мес", "Безопасный лимит скрапинга на 1 аккаунт до бана"],
    ["Общие Инструменты", "Master Apollo", 99, "$/мес", "Стоимость 1 аккаунта Apollo"],
    ["Общие Инструменты", "Лимит аккаунта Apollo", 2000, "кандидатов/мес", "Лимит кандидатов на 1 аккаунт Apollo"],
    ["Переменные (AI)", "Стоимость токенов AI", 0.002, "$/кандидат", "Затраты Gemini API на скоринг 1 кандидата"],
    ["Переменные", "Доля серверов на юзера", 5, "$/юзер", "Амортизация общих серверов на 1 клиента"],
    ["", "", "", "", ""],
    ["РАСПРЕДЕЛЕНИЕ ПРИБЫЛИ", "Доля на поддержку серверов", 0.3, "30%", "От чистой прибыли (по запросу Артема)"],
    ["РАСПРЕДЕЛЕНИЕ ПРИБЫЛИ", "Доля на развитие", 0.1, "10%", "От чистой прибыли"],
    ["РАСПРЕДЕЛЕНИЕ ПРИБЫЛИ", "Личная выручка", 0.6, "60%", "От чистой прибыли"],
    ["", "", "", "", ""],
    ["=== РАСЧЕТ ТАРИФОВ ===", "", "", "", "МЕНЯТЬ ЛИМИТЫ И ЦЕНУ МОЖНО ТУТ"],
    ["Название тарифа", "Цена для клиента ($)", "Лимит кандидатов", "Модель BYOT?", "Себестоимость ($)", "Чистая прибыль ($)", "Маржинальность (%)"]
]

df = pd.DataFrame(data)

# Create an Excel writer
with pd.ExcelWriter('/Users/imjustchilling/Desktop/sourcer/Financial_Model_Sourcer.xlsx', engine='openpyxl') as writer:
    df.to_excel(writer, index=False, header=False, sheet_name='Model')
    
    workbook = writer.book
    worksheet = writer.sheets['Model']
    
    # Add formulas for the tiers
    # Tier 1: Lite
    worksheet.cell(row=16, column=1, value="Tier 1: Lite (Shared)")
    worksheet.cell(row=16, column=2, value=149)
    worksheet.cell(row=16, column=3, value=500)
    worksheet.cell(row=16, column=4, value="Нет (мы парсим)")
    worksheet.cell(row=16, column=5, value="=(C16/C4)*C3 + (C16/C6)*C5 + (C16*C7) + C8") # Cost
    worksheet.cell(row=16, column=6, value="=B16-E16") # Profit
    worksheet.cell(row=16, column=7, value="=F16/B16") # Margin
    
    # Tier 2: Pro
    worksheet.cell(row=17, column=1, value="Tier 2: Pro (Shared)")
    worksheet.cell(row=17, column=2, value=299)
    worksheet.cell(row=17, column=3, value=1500)
    worksheet.cell(row=17, column=4, value="Нет (мы парсим)")
    worksheet.cell(row=17, column=5, value="=(C17/C4)*C3 + (C17/C6)*C5 + (C17*C7) + C8")
    worksheet.cell(row=17, column=6, value="=B17-E17")
    worksheet.cell(row=17, column=7, value="=F17/B17")
    
    # Tier 3: Enterprise
    worksheet.cell(row=18, column=1, value="Tier 3: Enterprise (BYOT)")
    worksheet.cell(row=18, column=2, value=599)
    worksheet.cell(row=18, column=3, value=5000)
    worksheet.cell(row=18, column=4, value="Да (клиент платит за свой Sales Nav)")
    worksheet.cell(row=18, column=5, value="=(C18*C7) + C8") # Only AI and server allocation
    worksheet.cell(row=18, column=6, value="=B18-E18")
    worksheet.cell(row=18, column=7, value="=F18/B18")

    # Format percentages
    for row in range(16, 19):
        worksheet.cell(row=row, column=7).number_format = '0.00%'

    # Adjust column widths
    worksheet.column_dimensions['A'].width = 30
    worksheet.column_dimensions['B'].width = 25
    worksheet.column_dimensions['C'].width = 20
    worksheet.column_dimensions['D'].width = 20
    worksheet.column_dimensions['E'].width = 30
    worksheet.column_dimensions['F'].width = 20
    worksheet.column_dimensions['G'].width = 20

print("Financial model created at /Users/imjustchilling/Desktop/sourcer/Financial_Model_Sourcer.xlsx")
