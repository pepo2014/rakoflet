import flet as ft
import qrcode
from datetime import datetime, timedelta
import random
import os
import cv2
from pyzbar import pyzbar
import pandas as pd
import sqlite3
import time
import threading
import webbrowser

# إنشاء مجلدات لتخزين الملفات
if not os.path.exists("students"):
    os.makedirs("students")
if not os.path.exists("reports"):
    os.makedirs("reports")

# إنشاء قاعدة البيانات
DATABASE_FILE = "attendance.db"

def create_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            time TEXT NOT NULL,
            days TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            group_name TEXT NOT NULL,
            attendance TEXT,
            evaluation TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dark_mode INTEGER DEFAULT 0,
            language TEXT DEFAULT 'ar'
        )
    ''')
    conn.commit()
    conn.close()

create_database()

class NotificationSystem:
    def __init__(self, page):
        self.page = page
        self.icon_map = {
            "success": ft.icons.CHECK_CIRCLE,
            "error": ft.icons.ERROR,
            "warning": ft.icons.WARNING,
            "info": ft.icons.INFO
        }
        self.color_map = {
            "success": ft.colors.GREEN,
            "error": ft.colors.RED,
            "warning": ft.colors.ORANGE,
            "info": ft.colors.BLUE
        }
        
    def show_notification(self, title, message, notification_type="info", duration=3000):
        notification = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(self.icon_map.get(notification_type, ft.icons.INFO)),
                ft.Text(title)
            ]),
            content=ft.Text(message),
            actions=[ft.TextButton("حسناً", on_click=lambda e: self.close_notification())],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = notification
        notification.open = True
        self.page.update()
        
        if duration > 0:
            def close_after_delay():
                time.sleep(duration/1000)
                if notification.open:
                    notification.open = False
                    self.page.update()
            
            threading.Thread(target=close_after_delay, daemon=True).start()
    
    def close_notification(self):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()
    
    def show_toast(self, message, notification_type="info"):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Row([
                ft.Icon(self.icon_map.get(notification_type, ft.icons.INFO)),
                ft.Text(message)
            ]),
            bgcolor=self.color_map.get(notification_type, ft.colors.BLUE),
            duration=3000,
            behavior=ft.SnackBarBehavior.FLOATING,
            elevation=10,
            shape=ft.RoundedRectangleBorder(radius=10)
        )
        self.page.snack_bar.open = True
        self.page.update()

class Student:
    def __init__(self, name, phone, group):
        self.id = None
        self.name = name
        self.phone = phone
        self.group = group
        self.attendance = []
        self.evaluation = {}

    def generate_qr_code(self, page):
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(str(self.id))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(f"students/{self.name}_QR.png")
            NotificationSystem(page).show_toast(f"تم إنشاء QR Code للطالب {self.name}", "success")
        except Exception as e:
            NotificationSystem(page).show_toast(f"خطأ في إنشاء QR Code: {str(e)}", "error")

class Group:
    def __init__(self, name, time, days):
        self.name = name
        self.time = time
        self.days = days
        self.students = []

    def add_student(self, student, page):
        self.students.append(student)
        NotificationSystem(page).show_toast(f"تمت إضافة الطالب {student.name} إلى المجموعة {self.name}", "success")

    def remove_student(self, student_id, page):
        for student in self.students:
            if student.id == student_id:
                self.students.remove(student)
                NotificationSystem(page).show_toast(f"تم حذف الطالب {student.name} من المجموعة {self.name}", "success")
                return
        NotificationSystem(page).show_toast("الطالب غير موجود في هذه المجموعة.", "error")

class AttendanceSystem:
    def __init__(self):
        self.groups = []
        self.students = []
        self.notification = None
        self.load_data()

    def load_data(self):
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM groups")
            groups = cursor.fetchall()
            for group in groups:
                self.groups.append(Group(group[1], group[2], group[3]))

            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()
            for student in students:
                new_student = Student(student[1], student[2], student[3])
                new_student.id = student[0]
                new_student.attendance = student[4].split(',') if student[4] else []
                new_student.evaluation = eval(student[5]) if student[5] else {}
                self.students.append(new_student)
            conn.close()
            print("تم تحميل البيانات بنجاح")
        except Exception as e:
            print(f"Error loading data: {str(e)}")

    def save_data(self):
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM groups")
            cursor.execute("DELETE FROM students")
            for group in self.groups:
                cursor.execute("INSERT INTO groups (name, time, days) VALUES (?, ?, ?)", 
                             (group.name, group.time, group.days))
            for student in self.students:
                cursor.execute("""INSERT INTO students (id, name, phone, group_name, attendance, evaluation) 
                               VALUES (?, ?, ?, ?, ?, ?)""",
                             (student.id, student.name, student.phone, student.group, 
                              ','.join(student.attendance), str(student.evaluation)))
            conn.commit()
            conn.close()
            print("تم حفظ البيانات بنجاح")
            return True
        except Exception as e:
            print(f"Error saving data: {str(e)}")
            return False

    def add_group(self, name, time, days, page):
        if any(group.name == name for group in self.groups):
            NotificationSystem(page).show_toast("هذه المجموعة موجودة بالفعل!", "error")
            return False

        new_group = Group(name, time, days)
        self.groups.append(new_group)
        if self.save_data():
            NotificationSystem(page).show_toast(f"تمت إضافة المجموعة: {name}", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء حفظ المجموعة!", "error")
            return False

    def add_student(self, name, phone, group_name, page):
        group = next((g for g in self.groups if g.name == group_name), None)
        if not group:
            NotificationSystem(page).show_toast("المجموعة غير موجودة!", "error")
            return False

        # توليد ID مكون من 5 أرقام بشكل فريد
        while True:
            student_id = random.randint(10000, 99999)
            if not any(s.id == student_id for s in self.students):
                break

        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO students (id, name, phone, group_name, attendance, evaluation) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                         (student_id, name, phone, group_name, '', '{}'))
            conn.commit()
            conn.close()

            new_student = Student(name, phone, group_name)
            new_student.id = student_id
            self.students.append(new_student)
            group.add_student(new_student, page)
            new_student.generate_qr_code(page)
            
            if self.save_data():
                NotificationSystem(page).show_toast(f"تمت إضافة الطالب: {name} (ID: {new_student.id})", "success")
                return True
            else:
                NotificationSystem(page).show_toast("حدث خطأ أثناء حفظ الطالب!", "error")
                return False
        except Exception as e:
            NotificationSystem(page).show_toast(f"خطأ في إضافة الطالب: {str(e)}", "error")
            return False

    def delete_student(self, student_id, page):
        student = next((s for s in self.students if s.id == student_id), None)
        if not student:
            NotificationSystem(page).show_toast("الطالب غير موجود!", "error")
            return False

        self.students.remove(student)
        if self.save_data():
            NotificationSystem(page).show_toast(f"تم حذف الطالب: {student.name}", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء حذف الطالب!", "error")
            return False

    def delete_group(self, group_name, page):
        group = next((g for g in self.groups if g.name == group_name), None)
        if not group:
            NotificationSystem(page).show_toast("المجموعة غير موجودة!", "error")
            return False

        # حذف جميع الطلاب في هذه المجموعة أولاً
        students_to_remove = [s for s in self.students if s.group == group_name]
        for student in students_to_remove:
            self.students.remove(student)

        self.groups.remove(group)
        if self.save_data():
            NotificationSystem(page).show_toast(f"تم حذف المجموعة: {group_name}", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء حذف المجموعة!", "error")
            return False

    def edit_student(self, student_id, new_name, new_phone, new_group, page):
        student = next((s for s in self.students if s.id == student_id), None)
        if not student:
            NotificationSystem(page).show_toast("الطالب غير موجود!", "error")
            return False

        old_group = next((g for g in self.groups if g.name == student.group), None)
        new_group_obj = next((g for g in self.groups if g.name == new_group), None)
        
        if not new_group_obj:
            NotificationSystem(page).show_toast("المجموعة الجديدة غير موجودة!", "error")
            return False

        # تحديث بيانات الطالب
        student.name = new_name
        student.phone = new_phone
        
        # إذا تغيرت المجموعة، نقوم بنقل الطالب
        if student.group != new_group:
            if old_group:
                old_group.students.remove(student)
            student.group = new_group
            new_group_obj.students.append(student)

        if self.save_data():
            NotificationSystem(page).show_toast(f"تم تعديل بيانات الطالب: {student.name}", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء تعديل بيانات الطالب!", "error")
            return False

    def edit_group(self, old_name, new_name, new_time, new_days, page):
        group = next((g for g in self.groups if g.name == old_name), None)
        if not group:
            NotificationSystem(page).show_toast("المجموعة غير موجودة!", "error")
            return False

        # التحقق من أن الاسم الجديد غير مستخدم (إذا تغير)
        if old_name != new_name and any(g.name == new_name for g in self.groups):
            NotificationSystem(page).show_toast("اسم المجموعة الجديد مستخدم بالفعل!", "error")
            return False

        # تحديث بيانات المجموعة
        group.name = new_name
        group.time = new_time
        group.days = new_days

        # تحديث مجموعة الطلاب المرتبطين
        for student in self.students:
            if student.group == old_name:
                student.group = new_name

        if self.save_data():
            NotificationSystem(page).show_toast(f"تم تعديل بيانات المجموعة: {group.name}", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء تعديل بيانات المجموعة!", "error")
            return False

    def record_attendance(self, student_id, page):
        student = next((s for s in self.students if s.id == student_id), None)
        if not student:
            NotificationSystem(page).show_toast("الطالب غير موجود!", "error")
            return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        group = next((g for g in self.groups if g.name == student.group), None)
        if not group:
            NotificationSystem(page).show_toast("المجموعة غير موجودة!", "error")
            return False
        
        group_days = group.days.split(',')
        today_name = datetime.now().strftime("%A")
        
        days_mapping = {
            "Saturday": "السبت",
            "Sunday": "الأحد",
            "Monday": "الاثنين",
            "Tuesday": "الثلاثاء",
            "Wednesday": "الأربعاء",
            "Thursday": "الخميس",
            "Friday": "الجمعة"
        }
        today_name_arabic = days_mapping.get(today_name, today_name)
        
        if today_name_arabic not in group_days:
            NotificationSystem(page).show_toast(f"اليوم ({today_name_arabic}) ليس من أيام المجموعة!", "error")
            return False
        
        if today in student.attendance:
            NotificationSystem(page).show_toast("تم تسجيل حضور هذا الطالب مسبقًا اليوم!", "error")
            return False
        
        student.attendance.append(today)
        if self.save_data():
            NotificationSystem(page).show_toast(f"تم تسجيل حضور الطالب {student.name} بتاريخ {today}", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء تسجيل الحضور!", "error")
            return False

    def evaluate_student(self, student_id, stars, notes, page):
        student = next((s for s in self.students if s.id == student_id), None)
        if not student:
            NotificationSystem(page).show_toast("الطالب غير موجود!", "error")
            return False
        
        today = datetime.now().strftime("%Y-%m-%d")
        student.evaluation[today] = {"stars": stars, "notes": notes}
        
        if self.save_data():
            NotificationSystem(page).show_toast(f"تم تقييم الطالب {student.name} بنجاح!", "success")
            return True
        else:
            NotificationSystem(page).show_toast("حدث خطأ أثناء حفظ التقييم!", "error")
            return False

    def generate_monthly_report(self, student_id, start_date, end_date, page):
        student = next((s for s in self.students if s.id == student_id), None)
        if not student:
            NotificationSystem(page).show_toast("الطالب غير موجود!", "error")
            return None

        group = next((g for g in self.groups if g.name == student.group), None)
        if not group:
            NotificationSystem(page).show_toast("المجموعة غير موجودة!", "error")
            return None

        group_days = group.days.split(',')
        data = {"التاريخ": [], "اليوم": [], "الحضور": [], "التقييم": [], "الملاحظات": []}
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            NotificationSystem(page).show_toast("صيغة التاريخ غير صحيحة! استخدم YYYY-MM-DD", "error")
            return None

        days_mapping = {
            "Saturday": "السبت",
            "Sunday": "الأحد",
            "Monday": "الاثنين",
            "Tuesday": "الثلاثاء",
            "Wednesday": "الأربعاء",
            "Thursday": "الخميس",
            "Friday": "الجمعة"
        }

        current_date = start
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%A")
            day_name_arabic = days_mapping.get(day_name, day_name)

            if day_name_arabic in group_days:
                data["التاريخ"].append(date_str)
                data["اليوم"].append(day_name_arabic)

                if date_str in student.attendance:
                    data["الحضور"].append("حاضر")
                    if date_str in student.evaluation:
                        data["التقييم"].append(student.evaluation[date_str]["stars"])
                        data["الملاحظات"].append(student.evaluation[date_str]["notes"])
                    else:
                        data["التقييم"].append("بدون تقييم")
                        data["الملاحظات"].append("بدون ملاحظات")
                else:
                    data["الحضور"].append("غائب")
                    data["التقييم"].append("بدون تقييم")
                    data["الملاحظات"].append("بدون ملاحظات")

            current_date += timedelta(days=1)

        total_days = len(data["التاريخ"])
        present_days = data["الحضور"].count("حاضر")
        absent_days = total_days - present_days
        attendance_percentage = (present_days / total_days) * 100 if total_days > 0 else 0
        absence_percentage = 100 - attendance_percentage if total_days > 0 else 0

        try:
            df = pd.DataFrame(data)
            file_path = f"reports/{student.name}_report.xlsx"
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='تقرير الحضور')
                workbook = writer.book
                worksheet = writer.sheets['تقرير الحضور']

                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#4CAF50',
                    'border': 1,
                    'font_color': 'white'
                })

                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

                cell_format_green = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                cell_format_red = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

                for row_num in range(1, len(df) + 1):
                    if df.iloc[row_num - 1]['الحضور'] == 'حاضر':
                        worksheet.set_row(row_num, None, cell_format_green)
                    else:
                        worksheet.set_row(row_num, None, cell_format_red)

                worksheet.write(len(df) + 2, 0, f"تقرير الحضور للطالب {student.name} (ID: {student.id})")
                worksheet.write(len(df) + 3, 0, f"نسبة الحضور: {attendance_percentage:.2f}%")
                worksheet.write(len(df) + 4, 0, f"نسبة الغياب: {absence_percentage:.2f}%")
                worksheet.write(len(df) + 5, 0, f"حضر: {present_days} مرة")
                worksheet.write(len(df) + 6, 0, f"غاب: {absent_days} مرة")

            NotificationSystem(page).show_toast(f"تم إنشاء التقرير بنجاح: {file_path}", "success")
            return file_path
        except Exception as e:
            NotificationSystem(page).show_toast(f"خطأ في إنشاء التقرير: {str(e)}", "error")
            return None

    def scan_qr_code(self, page):
        def close_camera(e=None):
            nonlocal cap
            if cap:
                cap.release()
            cv2.destroyAllWindows()
            if hasattr(page, 'dialog') and page.dialog.open:
                page.dialog.open = False
                page.update()

        cap = None
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                NotificationSystem(page).show_toast("تعذر الوصول إلى الكاميرا!", "error")
                return

            dlg = ft.AlertDialog(
                title=ft.Text("مسح QR Code"),
                content=ft.Column([
                    ft.Text("جارٍ مسح QR Code...", size=16),
                    ft.ElevatedButton(
                        "إلغاء",
                        on_click=close_camera,
                        color=ft.colors.WHITE,
                        bgcolor=ft.colors.RED
                    )
                ], tight=True),
                on_dismiss=lambda e: print("Dialog dismissed!")
            )
            
            page.dialog = dlg
            dlg.open = True
            page.update()

            while dlg.open:
                ret, frame = cap.read()
                if not ret:
                    NotificationSystem(page).show_toast("تعذر قراءة الصورة من الكاميرا!", "error")
                    break

                barcodes = pyzbar.decode(frame)
                for barcode in barcodes:
                    try:
                        student_id = int(barcode.data.decode("utf-8"))
                        self.record_attendance(student_id, page)
                        close_camera()
                        return
                    except Exception as e:
                        NotificationSystem(page).show_toast(f"خطأ في قراءة QR Code: {str(e)}", "error")
                        close_camera()
                        return

                cv2.imshow("QR Code Scanner", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            NotificationSystem(page).show_toast(f"خطأ في مسح QR Code: {str(e)}", "error")
        finally:
            close_camera()

    def generate_group_report(self, group_name, start_date, end_date, page):
        group = next((g for g in self.groups if g.name == group_name), None)
        if not group:
            NotificationSystem(page).show_toast("المجموعة غير موجودة!", "error")
            return None

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            NotificationSystem(page).show_toast("صيغة التاريخ غير صحيحة! استخدم YYYY-MM-DD", "error")
            return None

        data = {
            "الطالب": [],
            "الحضور (%)": [],
            "الغياب (%)": [],
            "الحضور (عدد)": [],
            "الغياب (عدد)": [],
            "متوسط التقييم": []
        }

        for student in group.students:
            attendance_days = [d for d in student.attendance 
                             if start <= datetime.strptime(d, "%Y-%m-%d") <= end]
            
            total_possible_days = len(group.days.split(',')) * ((end - start).days // 7 + 1)
            present_days = len(attendance_days)
            attendance_percentage = (present_days / total_possible_days) * 100 if total_possible_days > 0 else 0
            absence_percentage = 100 - attendance_percentage if total_possible_days > 0 else 0
            
            evaluations = [eval_data["stars"] for eval_data in student.evaluation.values()]
            avg_evaluation = sum(evaluations) / len(evaluations) if evaluations else 0

            data["الطالب"].append(student.name)
            data["الحضور (%)"].append(f"{attendance_percentage:.2f}%")
            data["الغياب (%)"].append(f"{absence_percentage:.2f}%")
            data["الحضور (عدد)"].append(present_days)
            data["الغياب (عدد)"].append(total_possible_days - present_days)
            data["متوسط التقييم"].append(f"{avg_evaluation:.1f}")

        try:
            df = pd.DataFrame(data)
            file_path = f"reports/{group.name}_group_report.xlsx"
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='تقرير المجموعة')
                workbook = writer.book
                worksheet = writer.sheets['تقرير المجموعة']

                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#4CAF50',
                    'border': 1,
                    'font_color': 'white'
                })

                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

                cell_format_green = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                cell_format_red = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

                for row_num in range(1, len(df) + 1):
                    if float(df.iloc[row_num - 1]['الحضور (%)'].strip('%')) >= 50:
                        worksheet.set_row(row_num, None, cell_format_green)
                    else:
                        worksheet.set_row(row_num, None, cell_format_red)

                worksheet.write(len(df) + 2, 0, f"تقرير المجموعة {group.name}")
                worksheet.write(len(df) + 3, 0, f"من {start_date} إلى {end_date}")

            NotificationSystem(page).show_toast(f"تم إنشاء تقرير المجموعة بنجاح: {file_path}", "success")
            return file_path
        except Exception as e:
            NotificationSystem(page).show_toast(f"خطأ في إنشاء تقرير المجموعة: {str(e)}", "error")
            return None

    def export_students_list(self, page):
        try:
            data = {
                "الطالب": [],
                "ID": [],
                "المجموعة": [],
                "رقم الهاتف": [],
                "عدد أيام الحضور": [],
                "آخر تقييم": []
            }
            
            for student in self.students:
                data["الطالب"].append(student.name)
                data["ID"].append(student.id)
                data["المجموعة"].append(student.group)
                data["رقم الهاتف"].append(student.phone)
                data["عدد أيام الحضور"].append(len(student.attendance))
                
                if student.evaluation:
                    last_eval_date = max(student.evaluation.keys())
                    data["آخر تقييم"].append(student.evaluation[last_eval_date]["stars"])
                else:
                    data["آخر تقييم"].append("بدون تقييم")

            df = pd.DataFrame(data)
            file_path = os.path.abspath("reports/students_list.xlsx")
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='قائمة الطلاب')
                workbook = writer.book
                worksheet = writer.sheets['قائمة الطلاب']

                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'align': 'center',
                    'valign': 'vcenter',
                    'fg_color': '#4CAF50',
                    'border': 1,
                    'font_color': 'white'
                })

                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

            NotificationSystem(page).show_toast(f"تم تصدير قائمة الطلاب بنجاح إلى: {file_path}", "success")
            return file_path
        except Exception as e:
            NotificationSystem(page).show_toast(f"خطأ في تصدير قائمة الطلاب: {str(e)}", "error")
            return None

class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.notification = NotificationSystem(page)
        self.entry_student_id = ft.TextField()
        self.start_date_picker = ft.TextField()
        self.end_date_picker = ft.TextField()
        self.group_dropdown = ft.Dropdown()
        self.entry_report_id = ft.TextField()
        self.dark_mode = False
        self.load_settings()
        self.setup_page()
        self.system = AttendanceSystem()
        self.create_main_menu()
    
    def load_settings(self):
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM settings LIMIT 1")
            settings = cursor.fetchone()
            if settings:
                self.dark_mode = bool(settings[1])
            else:
                cursor.execute("INSERT INTO settings (dark_mode, language) VALUES (0, 'ar')")
                conn.commit()
                self.dark_mode = False
            conn.close()
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
            self.dark_mode = False
    
    def save_settings(self):
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET dark_mode=?", (int(self.dark_mode),))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving settings: {str(e)}")
            return False
    
    def setup_page(self):
        self.page.title = "SmartAttendance"
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=ft.colors.TEAL,
                secondary=ft.colors.CYAN,
                surface=ft.colors.WHITE,
            ),
            font_family="Tajawal"
        )
        self.page.theme_mode = ft.ThemeMode.LIGHT if not self.dark_mode else ft.ThemeMode.DARK
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.window_width = 1200
        self.page.window_height = 800
        self.page.window_min_width = 1000
        self.page.window_min_height = 700
        self.page.on_close = self.on_window_close
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.padding = 20
        self.page.bgcolor = ft.colors.GREY_50 if not self.dark_mode else ft.colors.GREY_900
    
    def toggle_dark_mode(self, e=None):
        self.dark_mode = not self.dark_mode
        self.save_settings()
        self.setup_page()
        self.page.update()
        self.notification.show_toast(f"تم تفعيل الوضع {'الداكن' if self.dark_mode else 'الفاتح'}", "success")
    
    def on_window_close(self):
        cv2.destroyAllWindows()
        self.page.window_destroy()
    
    def show_about_dialog(self, e=None):
        about_content = ft.Column([
            ft.Text("SmartAttendance", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("نظام إدارة الحضور الذكي", size=18),
            ft.Divider(),
            ft.Text("إصدار 1.0.0", size=16),
            ft.Text("تم التطوير بواسطة Pavly Hany", size=16),
            ft.Text("جميع الحقوق محفوظة © 2023", size=14),
            ft.Row([
                ft.ElevatedButton(
                    "زيارة الموقع",
                    icon=ft.icons.LANGUAGE,
                    on_click=lambda e: webbrowser.open("https://example.com")
                ),
                ft.ElevatedButton(
                    "إغلاق",
                    icon=ft.icons.CLOSE,
                    on_click=lambda e: self.close_dialog()
                )
            ], spacing=10)
        ], spacing=10)
        
        about_dialog = ft.AlertDialog(
            title=ft.Text("حول البرنامج"),
            content=about_content,
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = about_dialog
        about_dialog.open = True
        self.page.update()
    
    def show_settings_page(self, e=None):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.SETTINGS, size=30, color=ft.colors.WHITE),
                ft.Text("إعدادات البرنامج", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_700,
            border_radius=10,
            width=self.page.width
        )
        
        dark_mode_switch = ft.Switch(
            label="الوضع الداكن",
            value=self.dark_mode,
            on_change=self.toggle_dark_mode
        )
        
        language_dropdown = ft.Dropdown(
            label="اللغة",
            options=[
                ft.dropdown.Option("ar", "العربية"),
                ft.dropdown.Option("en", "English")
            ],
            value="ar",
            width=200
        )
        
        settings_form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("الإعدادات العامة:", size=18, weight=ft.FontWeight.BOLD),
                    dark_mode_switch,
                    language_dropdown,
                    ft.Divider(),
                    ft.Text("حول البرنامج:", size=18, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton(
                        "عرض معلومات البرنامج",
                        icon=ft.icons.INFO,
                        on_click=self.show_about_dialog
                    )
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        footer = ft.Container(
            content=ft.Row([
                ft.OutlinedButton(
                    text="رجوع",
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda e: self.create_main_menu(),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=20
                    )
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=10
        )
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                settings_form,
                footer
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()
    
    def create_main_menu(self):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.SCHOOL, size=40, color=ft.colors.WHITE),
                ft.Text("SmartAttendance", 
                       size=28, 
                       weight=ft.FontWeight.BOLD,
                       color=ft.colors.WHITE),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.icons.DARK_MODE if not self.dark_mode else ft.icons.LIGHT_MODE,
                    on_click=self.toggle_dark_mode,
                    tooltip="تبديل الوضع الداكن/الفاتح",
                    icon_color=ft.colors.WHITE
                )
            ]),
            padding=20,
            bgcolor=ft.colors.TEAL,
            border_radius=10,
            width=self.page.width
        )
        
        menu_cards = [
            {
                "title": "إضافة مجموعة",
                "icon": ft.icons.GROUP_ADD,
                "color": ft.colors.TEAL_300,
                "action": self.add_group_page
            },
            {
                "title": "إضافة طالب",
                "icon": ft.icons.PERSON_ADD,
                "color": ft.colors.CYAN_300,
                "action": self.add_student_page
            },
            {
                "title": "إدارة المجموعات",
                "icon": ft.icons.GROUP,
                "color": ft.colors.AMBER_300,
                "action": self.manage_groups_page
            },
            {
                "title": "إدارة الطلاب",
                "icon": ft.icons.PEOPLE,
                "color": ft.colors.PURPLE_300,
                "action": self.manage_students_page
            },
            {
                "title": "تسجيل الحضور",
                "icon": ft.icons.CHECK_CIRCLE,
                "color": ft.colors.LIGHT_GREEN_300,
                "action": self.record_attendance_page
            },
            {
                "title": "التقرير الشهري",
                "icon": ft.icons.ASSIGNMENT,
                "color": ft.colors.INDIGO_300,
                "action": self.generate_report_page
            },
            {
                "title": "تقرير المجموعة",
                "icon": ft.icons.ANALYTICS,
                "color": ft.colors.BLUE_GREY_300,
                "action": self.group_report_page
            },
            {
                "title": "طريقة الاستخدام",
                "icon": ft.icons.HELP,
                "color": ft.colors.DEEP_ORANGE_300,
                "action": self.how_to_use_page
            }
        ]
        
        cards_row = ft.ResponsiveRow(
            columns=12,
            spacing=20,
            run_spacing=20,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Icon(card["icon"], size=40, color=ft.colors.WHITE),
                        ft.Text(card["title"], size=18, color=ft.colors.WHITE)
                    ], 
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER),
                    padding=20,
                    border_radius=10,
                    bgcolor=card["color"],
                    on_click=card["action"],
                    col={"sm": 6, "md": 4, "lg": 3},
                    height=150,
                    ink=True,
                    animate=ft.animation.Animation(300, "easeInOut")
                ) for card in menu_cards
            ]
        )
        
        footer = ft.Container(
            content=ft.Row([
                ft.Text("تم التطوير بواسطة Pavly Hany", size=14, color=ft.colors.GREY_600),
                ft.PopupMenuButton(
                    items=[
                        ft.PopupMenuItem(text="إعدادات", icon=ft.icons.SETTINGS, on_click=self.show_settings_page),
                        ft.PopupMenuItem(text="حول البرنامج", icon=ft.icons.INFO, on_click=self.show_about_dialog),
                        ft.PopupMenuItem(text="تسجيل خروج", icon=ft.icons.EXIT_TO_APP, on_click=lambda e: self.page.window_close())
                    ]
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=10,
            border_radius=10,
            width=self.page.width
        )
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                cards_row,
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                footer
            ], 
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def add_group_page(self, e=None):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.GROUP_ADD, size=30, color=ft.colors.WHITE),
                ft.Text("إضافة مجموعة جديدة", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.TEAL_300,
            border_radius=10,
            width=self.page.width
        )
        
        self.entry_name = ft.TextField(
            label="اسم المجموعة",
            prefix_icon=ft.icons.TEXT_FIELDS,
            border_radius=10,
            filled=True,
            expand=True
        )
        
        self.entry_time = ft.TextField(
            label="وقت المجموعة (مثال: 10:00 صباحاً)",
            prefix_icon=ft.icons.ACCESS_TIME,
            border_radius=10,
            filled=True,
            expand=True
        )
        
        days = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        self.day_checkboxes = [
            ft.Checkbox(label=day, value=False) for day in days
        ]
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.entry_name,
                    self.entry_time,
                    ft.Text("أيام المجموعة:", size=18),
                    ft.Column(self.day_checkboxes, spacing=5)
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="حفظ",
                icon=ft.icons.SAVE,
                on_click=self.save_group,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="إلغاء",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.create_main_menu(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def save_group(self, e):
        name = self.entry_name.value.strip()
        time = self.entry_time.value.strip()
        selected_days = [day.label for day in self.day_checkboxes if day.value]
        days = ",".join(selected_days)
        
        if not name:
            self.notification.show_toast("يجب إدخال اسم المجموعة!", "error")
            return
        
        if not time:
            self.notification.show_toast("يجب إدخال وقت المجموعة!", "error")
            return
        
        if not days:
            self.notification.show_toast("يجب اختيار يوم واحد على الأقل!", "error")
            return
        
        if self.system.add_group(name, time, days, self.page):
            self.create_main_menu()

    def add_student_page(self, e=None):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.PERSON_ADD, size=30, color=ft.colors.WHITE),
                ft.Text("إضافة طالب جديد", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.CYAN_300,
            border_radius=10,
            width=self.page.width
        )
        
        self.entry_student_name = ft.TextField(
            label="اسم الطالب",
            prefix_icon=ft.icons.PERSON,
            border_radius=10,
            filled=True,
            expand=True
        )
        
        self.entry_phone = ft.TextField(
            label="رقم الهاتف",
            prefix_icon=ft.icons.PHONE,
            keyboard_type=ft.KeyboardType.PHONE,
            border_radius=10,
            filled=True,
            expand=True
        )
        
        groups = [group.name for group in self.system.groups]
        if not groups:
            self.notification.show_toast("لا توجد مجموعات متاحة! يرجى إضافة مجموعة أولاً.", "error")
            self.create_main_menu()
            return
            
        self.group_dropdown = ft.Dropdown(
            label="اختر المجموعة",
            prefix_icon=ft.icons.GROUP,
            options=[ft.dropdown.Option(group) for group in groups],
            border_radius=10,
            filled=True,
            expand=True
        )
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.entry_student_name,
                    self.entry_phone,
                    self.group_dropdown
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="حفظ",
                icon=ft.icons.SAVE,
                on_click=self.save_student,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="إلغاء",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.create_main_menu(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def save_student(self, e):
        name = self.entry_student_name.value.strip()
        phone = self.entry_phone.value.strip()
        group = self.group_dropdown.value
        
        if not name:
            self.notification.show_toast("يجب إدخال اسم الطالب!", "error")
            return
        
        if not phone:
            self.notification.show_toast("يجب إدخال رقم الهاتف!", "error")
            return
        
        if not group:
            self.notification.show_toast("يجب اختيار المجموعة!", "error")
            return
        
        if self.system.add_student(name, phone, group, self.page):
            self.create_main_menu()

    def manage_groups_page(self, e=None):
        self.page.clean()
        
        if not self.system.groups:
            self.notification.show_toast("لا توجد مجموعات متاحة!", "error")
            self.create_main_menu()
            return
            
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.GROUP, size=30, color=ft.colors.WHITE),
                ft.Text("إدارة المجموعات", size=24, color=ft.colors.WHITE),
                ft.Container(expand=True),
                ft.Text(f"عدد المجموعات: {len(self.system.groups)}", 
                       size=16, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.AMBER_300,
            border_radius=10,
            width=self.page.width
        )
        
        groups_list = ft.ListView(expand=True, spacing=10)
        
        for group in self.system.groups:
            group_card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.ListTile(
                            leading=ft.Icon(ft.icons.GROUP, color=ft.colors.AMBER),
                            title=ft.Text(group.name, weight=ft.FontWeight.BOLD),
                            subtitle=ft.Text(f"الوقت: {group.time} | الأيام: {group.days}"),
                        ),
                        ft.Row([
                            ft.FilledButton(
                                "تعديل",
                                icon=ft.icons.EDIT,
                                on_click=lambda e, g=group.name: self.edit_group_page(g),
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    padding=10
                                )
                            ),
                            ft.FilledButton(
                                "حذف",
                                icon=ft.icons.DELETE,
                                on_click=lambda e, g=group.name: self.delete_group(g),
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    padding=10,
                                    bgcolor=ft.colors.RED
                                )
                            )
                        ], spacing=10)
                    ]),
                    padding=10,
                    border_radius=ft.border_radius.all(10)
                ),
                elevation=5
            )
            groups_list.controls.append(group_card)
        
        footer = ft.Container(
            content=ft.Row([
                ft.OutlinedButton(
                    text="رجوع للقائمة الرئيسية",
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda e: self.create_main_menu(),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=20
                    )
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=10
        )
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                ft.Container(
                    content=groups_list,
                    border_radius=10,
                    padding=10,
                    bgcolor=ft.colors.WHITE,
                    shadow=ft.BoxShadow(
                        spread_radius=1,
                        blur_radius=5,
                        color=ft.colors.GREY_300,
                        offset=ft.Offset(0, 0)
                    ),
                    expand=True
                ),
                footer
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def edit_group_page(self, group_name):
        self.page.clean()
        
        group = next((g for g in self.system.groups if g.name == group_name), None)
        if not group:
            self.notification.show_toast("المجموعة غير موجودة!", "error")
            self.manage_groups_page()
            return
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.EDIT, size=30, color=ft.colors.WHITE),
                ft.Text(f"تعديل المجموعة: {group_name}", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.TEAL_300,
            border_radius=10,
            width=self.page.width
        )
        
        self.entry_name = ft.TextField(
            label="اسم المجموعة",
            prefix_icon=ft.icons.TEXT_FIELDS,
            border_radius=10,
            filled=True,
            value=group.name,
            expand=True
        )
        
        self.entry_time = ft.TextField(
            label="وقت المجموعة",
            prefix_icon=ft.icons.ACCESS_TIME,
            border_radius=10,
            filled=True,
            value=group.time,
            expand=True
        )
        
        days = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        current_days = group.days.split(',')
        self.day_checkboxes = [
            ft.Checkbox(label=day, value=day in current_days) for day in days
        ]
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.entry_name,
                    self.entry_time,
                    ft.Text("أيام المجموعة:", size=18),
                    ft.Column(self.day_checkboxes, spacing=5)
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="حفظ التعديلات",
                icon=ft.icons.SAVE,
                on_click=lambda e: self.save_group_edit(group_name),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="إلغاء",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.manage_groups_page(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def save_group_edit(self, old_name):
        new_name = self.entry_name.value.strip()
        new_time = self.entry_time.value.strip()
        selected_days = [day.label for day in self.day_checkboxes if day.value]
        new_days = ",".join(selected_days)
        
        if not new_name:
            self.notification.show_toast("يجب إدخال اسم المجموعة!", "error")
            return
        
        if not new_time:
            self.notification.show_toast("يجب إدخال وقت المجموعة!", "error")
            return
        
        if not new_days:
            self.notification.show_toast("يجب اختيار يوم واحد على الأقل!", "error")
            return
        
        if self.system.edit_group(old_name, new_name, new_time, new_days, self.page):
            self.manage_groups_page()

    def delete_group(self, group_name):
        def confirm_delete(e):
            if self.system.delete_group(group_name, self.page):
                self.manage_groups_page()
            dlg_modal.open = False
            self.page.update()
        
        def cancel_delete(e):
            dlg_modal.open = False
            self.page.update()
        
        dlg_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("تأكيد الحذف"),
            content=ft.Text(f"هل أنت متأكد من حذف المجموعة '{group_name}'؟ سيتم حذف جميع الطلاب المرتبطين بها."),
            actions=[
                ft.TextButton("نعم", on_click=confirm_delete),
                ft.TextButton("لا", on_click=cancel_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dlg_modal
        dlg_modal.open = True
        self.page.update()

    def manage_students_page(self, e=None):
        self.page.clean()
        
        if not self.system.students:
            self.notification.show_toast("لا يوجد طلاب مسجلين!", "error")
            self.create_main_menu()
            return
            
        header = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.PEOPLE, size=30, color=ft.colors.WHITE),
                    ft.Text("إدارة الطلاب", size=24, color=ft.colors.WHITE),
                    ft.Container(expand=True),
                    ft.TextField(
                        width=300,
                        height=40,
                        hint_text="ابحث عن طالب...",
                        on_change=self.filter_students
                    )
                ]),
                ft.Row([
                    ft.Text(f"عدد الطلاب: {len(self.system.students)}", 
                           size=16, color=ft.colors.WHITE),
                    ft.Container(expand=True),
                    ft.FilledButton(
                        "تصدير القائمة",
                        icon=ft.icons.DOWNLOAD,
                        on_click=self.download_students_list,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=10
                        )
                    )
                ])
            ]),
            padding=15,
            bgcolor=ft.colors.PURPLE_300,
            border_radius=10,
            width=self.page.width
        )
        
        students_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("الاسم")),
                ft.DataColumn(ft.Text("المجموعة")),
                ft.DataColumn(ft.Text("الحضور")),
                ft.DataColumn(ft.Text("آخر تقييم")),
                ft.DataColumn(ft.Text("إجراءات"))
            ],
            rows=[
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(student.id)),
                        ft.DataCell(ft.Text(student.name)),
                        ft.DataCell(ft.Text(student.group)),
                        ft.DataCell(ft.Text(f"{len(student.attendance)} يوم")),
                        ft.DataCell(
                            ft.Row([
                                ft.Icon(ft.icons.STAR, 
                                    color=ft.colors.AMBER, 
                                    size=16) for _ in range(
                                        int(student.evaluation.get(
                                            max(student.evaluation.keys(), "")
                                                ).get("stars", 0))
                                    )
                            ]) if student.evaluation else ft.Text("بدون")
                        ),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_color=ft.colors.BLUE,
                                    tooltip="تعديل",
                                    on_click=lambda e, s=student.id: self.edit_student_page(s)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.STAR,
                                    icon_color=ft.colors.AMBER,
                                    tooltip="تقييم",
                                    on_click=lambda e, s=student.id: self.evaluate_student_page(s)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color=ft.colors.RED,
                                    tooltip="حذف",
                                    on_click=lambda e, s=student.id: self.delete_student(s)
                                )
                            ], spacing=5)
                        )
                    ]
                ) for student in self.system.students
            ],
            border=ft.border.all(1, ft.colors.GREY_300),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, ft.colors.GREY_300),
            horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_300),
            heading_row_color=ft.colors.GREY_200,
            heading_row_height=50,
            data_row_min_height=60,
            expand=True
        )
        
        footer = ft.Container(
            content=ft.Row([
                ft.OutlinedButton(
                    text="رجوع للقائمة الرئيسية",
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda e: self.create_main_menu(),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=20
                    )
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=10
        )
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                ft.Container(
                    content=students_table,
                    border_radius=10,
                    padding=10,
                    bgcolor=ft.colors.WHITE,
                    shadow=ft.BoxShadow(
                        spread_radius=1,
                        blur_radius=5,
                        color=ft.colors.GREY_300,
                        offset=ft.Offset(0, 0)
                    ),
                    expand=True
                ),
                footer
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def filter_students(self, e):
        search_text = e.control.value.lower()
        filtered_students = [s for s in self.system.students 
                            if search_text in s.name.lower() 
                            or search_text in str(s.id)
                            or search_text in s.group.lower()]
        
        # سيتم تطبيق البحث هنا عند تنفيذ الوظيفة
        pass

    def download_students_list(self, e):
        file_path = self.system.export_students_list(self.page)
        if file_path:
            self.notification.show_toast(f"تم تنزيل قائمة الطلاب بنجاح في: {file_path}", "success")

    def edit_student_page(self, student_id):
        self.page.clean()
        
        student = next((s for s in self.system.students if s.id == student_id), None)
        if not student:
            self.notification.show_toast("الطالب غير موجود!", "error")
            self.manage_students_page()
            return
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.EDIT, size=30, color=ft.colors.WHITE),
                ft.Text(f"تعديل بيانات الطالب: {student.name}", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.BLUE_300,
            border_radius=10,
            width=self.page.width
        )
        
        self.entry_student_name = ft.TextField(
            label="اسم الطالب",
            prefix_icon=ft.icons.PERSON,
            border_radius=10,
            filled=True,
            value=student.name,
            expand=True
        )
        
        self.entry_phone = ft.TextField(
            label="رقم الهاتف",
            prefix_icon=ft.icons.PHONE,
            value=student.phone,
            keyboard_type=ft.KeyboardType.PHONE,
            border_radius=10,
            filled=True,
            expand=True
        )
        
        groups = [group.name for group in self.system.groups]
        self.group_dropdown = ft.Dropdown(
            label="اختر المجموعة",
            prefix_icon=ft.icons.GROUP,
            options=[ft.dropdown.Option(group) for group in groups],
            border_radius=10,
            filled=True,
            value=student.group,
            expand=True
        )
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.entry_student_name,
                    self.entry_phone,
                    self.group_dropdown
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="حفظ التعديلات",
                icon=ft.icons.SAVE,
                on_click=lambda e: self.save_student_edit(student_id),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="إلغاء",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.manage_students_page(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def save_student_edit(self, student_id):
        new_name = self.entry_student_name.value.strip()
        new_phone = self.entry_phone.value.strip()
        new_group = self.group_dropdown.value
        
        if not new_name:
            self.notification.show_toast("يجب إدخال اسم الطالب!", "error")
            return
        
        if not new_phone:
            self.notification.show_toast("يجب إدخال رقم الهاتف!", "error")
            return
        
        if not new_group:
            self.notification.show_toast("يجب اختيار المجموعة!", "error")
            return
        
        if self.system.edit_student(student_id, new_name, new_phone, new_group, self.page):
            self.manage_students_page()

    def evaluate_student_page(self, student_id):
        self.page.clean()
        
        student = next((s for s in self.system.students if s.id == student_id), None)
        if not student:
            self.notification.show_toast("الطالب غير موجود!", "error")
            self.manage_students_page()
            return
        
        self.student_id = student_id
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.STAR, size=30, color=ft.colors.WHITE),
                ft.Text(f"تقييم الطالب: {student.name}", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.AMBER_300,
            border_radius=10,
            width=self.page.width
        )
        
        self.entry_stars = ft.TextField(
            label="عدد النجوم (من 1 إلى 3)",
            prefix_icon=ft.icons.STAR,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"[1-3]"),
            border_radius=10,
            filled=True,
            expand=True
        )
        
        self.entry_notes = ft.TextField(
            label="ملاحظات",
            prefix_icon=ft.icons.NOTE,
            multiline=True,
            min_lines=3,
            border_radius=10,
            filled=True,
            expand=True
        )
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.entry_stars,
                    self.entry_notes
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="حفظ التقييم",
                icon=ft.icons.SAVE,
                on_click=self.save_evaluation,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="إلغاء",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.manage_students_page(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def save_evaluation(self, e):
        stars = self.entry_stars.value.strip()
        notes = self.entry_notes.value.strip()
        
        if not stars:
            self.notification.show_toast("يجب إدخال عدد النجوم!", "error")
            return
        
        if not notes:
            self.notification.show_toast("يجب إدخال الملاحظات!", "error")
            return
        
        try:
            stars_int = int(stars)
            if stars_int < 1 or stars_int > 3:
                self.notification.show_toast("عدد النجوم يجب أن يكون بين 1 و 3!", "error")
                return
        except ValueError:
            self.notification.show_toast("عدد النجوم يجب أن يكون رقماً بين 1 و 3!", "error")
            return
        
        if self.system.evaluate_student(self.student_id, stars_int, notes, self.page):
            self.manage_students_page()

    def delete_student(self, student_id):
        def confirm_delete(e):
            if self.system.delete_student(student_id, self.page):
                self.manage_students_page()
            dlg_modal.open = False
            self.page.update()
        
        def cancel_delete(e):
            dlg_modal.open = False
            self.page.update()
        
        student = next((s for s in self.system.students if s.id == student_id), None)
        if not student:
            self.notification.show_toast("الطالب غير موجود!", "error")
            return
            
        dlg_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("تأكيد الحذف"),
            content=ft.Text(f"هل أنت متأكد من حذف الطالب '{student.name}'؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm_delete),
                ft.TextButton("لا", on_click=cancel_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dlg_modal
        dlg_modal.open = True
        self.page.update()

    def record_attendance_page(self, e=None):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.CHECK_CIRCLE, size=30, color=ft.colors.WHITE),
                ft.Text("تسجيل الحضور", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.LIGHT_GREEN_300,
            border_radius=10,
            width=self.page.width
        )
        
        qr_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.QR_CODE, size=50, color=ft.colors.TEAL),
                    ft.Text("مسح QR Code", size=18),
                    ft.Text("استخدم كاميرا الجهاز لمسح كود الطالب", size=14, color=ft.colors.GREY),
                    ft.FilledButton(
                        "بدء المسح",
                        icon=ft.icons.CAMERA_ALT,
                        on_click=lambda e: self.system.scan_qr_code(self.page),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=15
                        ),
                        width=200
                    )
                ], 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER),
                padding=30,
                alignment=ft.alignment.center
            ),
            elevation=5,
            width=300,
            height=250
        )
        
        manual_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.KEYBOARD, size=50, color=ft.colors.INDIGO),
                    ft.Text("تسجيل يدوي", size=18),
                    
                    self.entry_student_id,
                    ft.FilledButton(
                        "تسجيل الحضور",
                        icon=ft.icons.CHECK,
                        on_click=self.record_attendance,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=15
                        ),
                        width=200
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15),
                padding=30,
                alignment=ft.alignment.center
            ),
            elevation=5,
            width=300,
            height=250
        )
        
        stats_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.ANALYTICS, size=50, color=ft.colors.ORANGE),
                    ft.Text("إحصائيات اليوم", size=18),
                    ft.Text(datetime.now().strftime("%Y-%m-%d"), size=14, color=ft.colors.GREY),
                    ft.Divider(),
                    ft.Row([
                        ft.Column([
                            ft.Text("الحضور", size=14),
                            ft.Text("0", size=24, weight=ft.FontWeight.BOLD)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.VerticalDivider(),
                        ft.Column([
                            ft.Text("الغياب", size=14),
                            ft.Text("0", size=24, weight=ft.FontWeight.BOLD)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                    ], spacing=20)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15),
                padding=30,
                alignment=ft.alignment.center
            ),
            elevation=5,
            width=300,
            height=250
        )
        
        footer = ft.Container(
            content=ft.Row([
                ft.OutlinedButton(
                    text="رجوع للقائمة الرئيسية",
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda e: self.create_main_menu(),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=20
                    )
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=10
        )
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                ft.ResponsiveRow(
                    columns=12,
                    controls=[
                        ft.Container(qr_card, col={"sm": 12, "md": 4}),
                        ft.Container(manual_card, col={"sm": 12, "md": 4}),
                        ft.Container(stats_card, col={"sm": 12, "md": 4})
                    ],
                    spacing=20,
                    run_spacing=20
                ),
                ft.Divider(height=20),
                footer
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def pick_date(self, target_field):
        def on_date_selected(e):
            target_field.value = e.control.value.strftime("%Y-%m-%d")
            self.page.update()
            self.page.dialog.open = False
            self.page.update()

        date_picker = ft.DatePicker(
            on_change=on_date_selected,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31)
        )
        
        self.page.overlay.append(date_picker)
        self.page.update()
        
        date_picker.pick_date()

    def record_attendance(self, e):
        student_id = self.entry_student_id.value.strip()
        if not student_id:
            self.notification.show_toast("يجب إدخال ID الطالب!", "error")
            return
        
        try:
            student_id_int = int(student_id)
            if self.system.record_attendance(student_id_int, self.page):
                self.entry_student_id.value = ""
                self.page.update()
        except ValueError:
            self.notification.show_toast("ID الطالب يجب أن يكون رقماً صحيحاً!", "error")

    def generate_report_page(self, e=None):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.ASSIGNMENT, size=30, color=ft.colors.WHITE),
                ft.Text("التقرير الشهري", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.INDIGO_300,
            border_radius=10,
            width=self.page.width
        )
        
        today = datetime.now().strftime("%Y-%m-%d")
        first_day_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        self.start_date_picker = ft.TextField(
            label="تاريخ البداية",
            value=first_day_of_month,
            prefix_icon=ft.icons.CALENDAR_TODAY,
            border_radius=10,
            filled=True,
            read_only=True,
            expand=True,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_MONTH,
                on_click=lambda e: self.pick_date(self.start_date_picker)
            )
        )
        
        self.end_date_picker = ft.TextField(
            label="تاريخ النهاية",
            value=today,
            prefix_icon=ft.icons.CALENDAR_TODAY,
            border_radius=10,
            filled=True,
            read_only=True,
            expand=True,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_MONTH,
                on_click=lambda e: self.pick_date(self.end_date_picker)
            )
        )
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.entry_report_id,
                    ft.Text("فترة التقرير:", size=18),
                    self.start_date_picker,
                    self.end_date_picker
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="عرض التقرير",
                icon=ft.icons.VISIBILITY,
                on_click=self.generate_report,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.FilledButton(
                text="تنزيل التقرير",
                icon=ft.icons.DOWNLOAD,
                on_click=self.download_report,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="رجوع",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.create_main_menu(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def generate_report(self, e):
        student_id = self.entry_report_id.value.strip()
        start_date = self.start_date_picker.value.strip()
        end_date = self.end_date_picker.value.strip()
        
        if not student_id:
            self.notification.show_toast("يجب إدخال ID الطالب!", "error")
            return
        
        if not start_date or not end_date:
            self.notification.show_toast("يجب تحديد تاريخ البداية والنهاية!", "error")
            return
        
        try:
            student_id_int = int(student_id)
            self.system.generate_monthly_report(student_id_int, start_date, end_date, self.page)
        except ValueError:
            self.notification.show_toast("ID الطالب يجب أن يكون رقماً صحيحاً!", "error")

    def download_report(self, e):
        self.generate_report(e)

    def group_report_page(self, e=None):
        self.page.clean()
        
        if not self.system.groups:
            self.notification.show_toast("لا توجد مجموعات متاحة!", "error")
            self.create_main_menu()
            return
            
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.ANALYTICS, size=30, color=ft.colors.WHITE),
                ft.Text("تقرير المجموعة", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_300,
            border_radius=10,
            width=self.page.width
        )
        
        today = datetime.now().strftime("%Y-%m-%d")
        first_day_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        self.group_dropdown = ft.Dropdown(
            label="اختر المجموعة",
            prefix_icon=ft.icons.GROUP,
            options=[ft.dropdown.Option(group.name) for group in self.system.groups],
            border_radius=10,
            filled=True,
            expand=True
        )
        
        self.start_date_picker = ft.TextField(
            label="تاريخ البداية",
            value=first_day_of_month,
            prefix_icon=ft.icons.CALENDAR_TODAY,
            border_radius=10,
            filled=True,
            read_only=True,
            expand=True,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_MONTH,
                on_click=lambda e: self.pick_date(self.start_date_picker)
            )
        )
        
        self.end_date_picker = ft.TextField(
            label="تاريخ النهاية",
            value=today,
            prefix_icon=ft.icons.CALENDAR_TODAY,
            border_radius=10,
            filled=True,
            read_only=True,
            expand=True,
            suffix=ft.IconButton(
                icon=ft.icons.CALENDAR_MONTH,
                on_click=lambda e: self.pick_date(self.end_date_picker)
            )
        )
        
        form = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    self.group_dropdown,
                    ft.Text("فترة التقرير:", size=18),
                    self.start_date_picker,
                    self.end_date_picker
                ], spacing=15),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        controls = ft.Row([
            ft.FilledButton(
                text="عرض التقرير",
                icon=ft.icons.VISIBILITY,
                on_click=self.generate_group_report,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.FilledButton(
                text="تنزيل التقرير",
                icon=ft.icons.DOWNLOAD,
                on_click=self.download_group_report,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            ),
            ft.OutlinedButton(
                text="رجوع",
                icon=ft.icons.ARROW_BACK,
                on_click=lambda e: self.create_main_menu(),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=20
                )
            )
        ], spacing=20, alignment=ft.MainAxisAlignment.END)
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                form,
                ft.Divider(height=20),
                controls
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

    def generate_group_report(self, e):
        group_name = self.group_dropdown.value
        start_date = self.start_date_picker.value.strip()
        end_date = self.end_date_picker.value.strip()
        
        if not group_name:
            self.notification.show_toast("يجب اختيار المجموعة!", "error")
            return
        
        if not start_date or not end_date:
            self.notification.show_toast("يجب تحديد تاريخ البداية والنهاية!", "error")
            return
        
        self.system.generate_group_report(group_name, start_date, end_date, self.page)

    def download_group_report(self, e):
        self.generate_group_report(e)

    def how_to_use_page(self, e=None):
        self.page.clean()
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.HELP, size=30, color=ft.colors.WHITE),
                ft.Text("طريقة استخدام البرنامج", size=24, color=ft.colors.WHITE)
            ]),
            padding=15,
            bgcolor=ft.colors.DEEP_ORANGE_300,
            border_radius=10,
            width=self.page.width
        )
        
        instructions = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("1. إضافة مجموعة:", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("- اضغط على زر 'إضافة مجموعة' من القائمة الرئيسية"),
                    ft.Text("- أدخل اسم المجموعة ووقتها وأيامها"),
                    ft.Text("- اضغط على زر 'إضافة المجموعة' لحفظها"),
                    ft.Divider(),
                    
                    ft.Text("2. إضافة طالب:", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("- اضغط على زر 'إضافة طالب' من القائمة الرئيسية"),
                    ft.Text("- أدخل اسم الطالب ورقم هاتفه واختر مجموعته"),
                    ft.Text("- سيتم إنشاء QR Code للطالب تلقائياً"),
                    ft.Divider(),
                    
                    ft.Text("3. تسجيل الحضور:", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("- اضغط على زر 'تسجيل الحضور' من القائمة الرئيسية"),
                    ft.Text("- يمكنك مسح QR Code الطالب أو إدخال ID يدوياً"),
                    ft.Text("- سيتم تسجيل الحضور تلقائياً إذا كان اليوم من أيام المجموعة"),
                    ft.Divider(),
                    
                    ft.Text("4. إدارة الطلاب والمجموعات:", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("- يمكنك تعديل أو حذف الطلاب والمجموعات من صفحات الإدارة"),
                    ft.Text("- يمكنك إضافة تقييمات للطلاب من صفحة إدارة الطلاب"),
                    ft.Divider(),
                    
                    ft.Text("5. التقارير:", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("- يمكنك إنشاء تقارير شهرية لكل طالب أو للمجموعة ككل"),
                    ft.Text("- يمكنك تنزيل التقارير كملفات Excel لمشاركتها"),
                    ft.Divider(),
                    
                    ft.Text("تم التطوير بواسطة", size=14),
                    ft.Text("Pavly Hany", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.DEEP_ORANGE)
                ], spacing=10),
                padding=20
            ),
            elevation=5,
            width=self.page.width
        )
        
        footer = ft.Container(
            content=ft.Row([
                ft.OutlinedButton(
                    text="رجوع للقائمة الرئيسية",
                    icon=ft.icons.ARROW_BACK,
                    on_click=lambda e: self.create_main_menu(),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=20
                    )
                )
            ], alignment=ft.MainAxisAlignment.START),
            padding=10
        )
        
        self.page.add(
            ft.Column([
                header,
                ft.Divider(height=20),
                instructions,
                footer
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO)
        )
        
        self.page.update()

def main(page: ft.Page):
    app = App(page)

ft.app(target=main, view=ft.AppView.FLET_APP)
