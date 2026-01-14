
from backend.services.tabel_service import format_initials

def test_format_initials():
    cases = [
        ("Петренко Тарас Степанович", "Петренко Т. С."),
        ("Іванов Іван", "Іванов І."),
        ("Сидоров", "Сидоров"),
        ("Someone With Many Names And Parts", "Someone W. M.") # Logic takes first 3 parts
    ]

    for input_name, expected in cases:
        result = format_initials(input_name)
        print(f"Input: {input_name} -> Output: {result} | Expected: {expected} | {'PASS' if result == expected else 'FAIL'}")

if __name__ == "__main__":
    test_format_initials()
