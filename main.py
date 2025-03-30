import flet as ft
import random

def main(page: ft.Page):
    page.title = "تغيير لون الخلفية"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    def change_color(e):
        random_color = f"#{random.randint(0, 0xFFFFFF):06x}"  # لون عشوائي
        page.bgcolor = random_color
        page.update()

    btn = ft.ElevatedButton("اضغط لتغيير اللون", on_click=change_color)
    page.add(btn)

ft.app(target=main)
