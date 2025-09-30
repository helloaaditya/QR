import io
import os
import secrets
from datetime import timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

import qrcode

from .models import AttendanceRecord, AttendanceSession, Student, Teacher, Subject


def home(request):
    # Only teachers should access the home/start page
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    teachers = Teacher.objects.all()
    subjects = Subject.objects.all()
    return render(request, 'attendance/home.html', {'teachers': teachers, 'subjects': subjects})


@require_http_methods(["POST"]) 
def start_session(request):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    duration_minutes = int(request.POST.get('duration', '2'))
    title = request.POST.get('title', 'Class Session')
    time_slot = request.POST.get('time_slot', '')
    teacher_id = request.POST.get('teacher')
    subject_id = request.POST.get('subject')
    if not all([title.strip(), time_slot.strip(), teacher_id, subject_id]):
        teachers = Teacher.objects.all()
        subjects = Subject.objects.all()
        return render(request, 'attendance/home.html', {
            'teachers': teachers,
            'subjects': subjects,
            'form_error': 'All fields are required'
        })
    code = secrets.token_urlsafe(8)
    now = timezone.now()
    session = AttendanceSession.objects.create(
        title=title,
        code=code,
        starts_at=now,
        ends_at=now + timedelta(minutes=duration_minutes),
        is_active=True,
        time_slot=time_slot,
        teacher=Teacher.objects.filter(id=teacher_id).first() if teacher_id else None,
        subject=Subject.objects.filter(id=subject_id).first() if subject_id else None,
    )
    return redirect('teacher_session', code=session.code)


def teacher_session(request, code: str):
    # Teacher guard: simple PIN in session
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    session = AttendanceSession.objects.get(code=code)
    return render(request, 'attendance/teacher_session.html', {'session': session})


def dashboard(request):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    sessions = AttendanceSession.objects.order_by('-starts_at')[:20]
    open_count = sum(1 for s in sessions if s.is_open)
    return render(request, 'attendance/dashboard.html', {'sessions': sessions, 'open_count': open_count})


def session_records_json(request, code: str):
    try:
        session = AttendanceSession.objects.get(code=code)
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'invalid session'}, status=404)
    data = [
        {
            'id': r.id,
            'student_id': r.student.student_id,
            'full_name': r.student.full_name,
            'scanned_at': r.scanned_at.isoformat(),
        }
        for r in session.records.order_by('-scanned_at')
    ]
    return JsonResponse({'ok': True, 'records': data, 'count': len(data)})


@require_http_methods(["POST"]) 
def delete_record(request, code: str):
    if request.session.get('teacher_authed') != True:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    try:
        session = AttendanceSession.objects.get(code=code)
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'invalid session'}, status=404)
    record_id = request.POST.get('record_id')
    if not record_id:
        return JsonResponse({'ok': False, 'error': 'record_id required'}, status=400)
    try:
        rec = AttendanceRecord.objects.get(id=record_id, session=session)
        rec.delete()
    except AttendanceRecord.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    return JsonResponse({'ok': True})


@require_http_methods(["POST"]) 
def delete_session(request, code: str):
    if request.session.get('teacher_authed') != True:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    try:
        sess = AttendanceSession.objects.get(code=code)
        sess.delete()
    except AttendanceSession.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    return JsonResponse({'ok': True})


def reports(request):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    # Filters
    teacher_id = request.GET.get('teacher') or ''
    subject_id = request.GET.get('subject') or ''
    date_from = request.GET.get('from') or ''
    date_to = request.GET.get('to') or ''

    sessions_qs = AttendanceSession.objects.all().order_by('-starts_at')
    if teacher_id:
        sessions_qs = sessions_qs.filter(teacher_id=teacher_id)
    if subject_id:
        sessions_qs = sessions_qs.filter(subject_id=subject_id)
    if date_from:
        sessions_qs = sessions_qs.filter(starts_at__date__gte=date_from)
    if date_to:
        sessions_qs = sessions_qs.filter(starts_at__date__lte=date_to)

    # Eager load counts
    sessions = list(sessions_qs)

    # CSV export
    if request.GET.get('export') == 'csv':
        import csv
        from django.utils.encoding import smart_str
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=attendance_report.csv'
        writer = csv.writer(response)
        writer.writerow(['Session Code','Title','Teacher','Subject','Slot','Start','End','Present Count'])
        for s in sessions:
            writer.writerow([
                smart_str(s.code), smart_str(s.title), smart_str(s.teacher or ''), smart_str(s.subject or ''),
                smart_str(s.time_slot or ''), s.starts_at, s.ends_at, s.records.count()
            ])
        return response

    teachers = Teacher.objects.all()
    subjects = Subject.objects.all()
    # Aggregate totals
    total_present = sum(s.records.count() for s in sessions)
    total_sessions = len(sessions)
    unique_devices = sum(s.unique_devices_count for s in sessions)
    # Chart data: present per subject and per teacher
    subject_to_count = {}
    teacher_to_count = {}
    for s in sessions:
        count = s.records.count()
        subj = str(s.subject or 'Unassigned')
        tch = str(s.teacher or 'Unassigned')
        subject_to_count[subj] = subject_to_count.get(subj, 0) + count
        teacher_to_count[tch] = teacher_to_count.get(tch, 0) + count
    chart = {
        'subjects': {
            'labels': list(subject_to_count.keys()),
            'counts': list(subject_to_count.values()),
        },
        'teachers': {
            'labels': list(teacher_to_count.keys()),
            'counts': list(teacher_to_count.values()),
        },
    }
    return render(request, 'attendance/reports.html', {
        'teachers': teachers,
        'subjects': subjects,
        'sessions': sessions,
        'filters': {
            'teacher': teacher_id,
            'subject': subject_id,
            'from': date_from,
            'to': date_to,
        },
        'metrics': {
            'total_present': total_present,
            'total_sessions': total_sessions,
            'unique_devices': unique_devices,
        },
        'chart': chart,
    })


def settings_students(request):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    if request.method == 'POST':
        # Create new student
        sid = (request.POST.get('student_id') or '').strip()
        name = (request.POST.get('full_name') or '').strip()
        if sid and name:
            Student.objects.get_or_create(student_id=sid, defaults={'full_name': name, 'is_active': True})
        return redirect('settings_students')
    # GET list
    students = Student.objects.order_by('student_id')
    teachers = Teacher.objects.order_by('full_name')
    subjects = Subject.objects.order_by('name')
    return render(request, 'attendance/settings_students.html', {
        'students': students,
        'teachers': teachers,
        'subjects': subjects,
    })


@require_http_methods(["POST"]) 
def settings_students_toggle(request):
    if request.session.get('teacher_authed') != True:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    sid = request.POST.get('student_id')
    try:
        s = Student.objects.get(student_id=sid)
        s.is_active = not s.is_active
        s.save(update_fields=['is_active'])
        return JsonResponse({'ok': True, 'is_active': s.is_active})
    except Student.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)


@require_http_methods(["POST"]) 
def settings_students_delete(request):
    if request.session.get('teacher_authed') != True:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    sid = request.POST.get('student_id')
    try:
        s = Student.objects.get(student_id=sid)
        s.delete()
        return JsonResponse({'ok': True})
    except Student.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)


@require_http_methods(["POST"]) 
def settings_teachers_add(request):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    name = (request.POST.get('full_name') or '').strip()
    if name:
        Teacher.objects.get_or_create(full_name=name)
    return redirect('settings_students')


@require_http_methods(["POST"]) 
def settings_teachers_delete(request):
    if request.session.get('teacher_authed') != True:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    tid = request.POST.get('id')
    try:
        t = Teacher.objects.get(id=tid)
        t.delete()
        return JsonResponse({'ok': True})
    except Teacher.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)


@require_http_methods(["POST"]) 
def settings_subjects_add(request):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    name = (request.POST.get('name') or '').strip()
    if name:
        Subject.objects.get_or_create(name=name)
    return redirect('settings_students')


@require_http_methods(["POST"]) 
def settings_subjects_delete(request):
    if request.session.get('teacher_authed') != True:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    sid = request.POST.get('id')
    try:
        s = Subject.objects.get(id=sid)
        s.delete()
        return JsonResponse({'ok': True})
    except Subject.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)


def qr_image(request, code: str):
    # Encodes a scan URL with the session code
    # Use your LAN IP for mobile access
    scan_url = f"http://10.68.17.134:8000/scan/{code}"
    
    # Generate QR with optimized settings
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Optimize response
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    response = HttpResponse(buf.getvalue(), content_type='image/png')
    
    # Prevent caching to ensure fresh QR codes
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Content-Length'] = str(len(buf.getvalue()))
    
    return response


def scan(request, code: str):
    # GET shows a simple form; POST records attendance
    students = Student.objects.filter(is_active=True).order_by('full_name', 'student_id')
    
    try:
        session = AttendanceSession.objects.get(code=code)
    except AttendanceSession.DoesNotExist:
        return render(request, 'attendance/scan.html', {
            'code': code, 
            'students': students,
            'message': 'Invalid session code', 
            'status': 'error'
        })

    if request.method == 'GET':
        return render(request, 'attendance/scan.html', {
            'code': code, 
            'students': students,
            'session': session
        })

    # POST - Handle attendance marking
    student_id = (request.POST.get('student_select') or request.POST.get('student_id') or '').strip()
    
    if not student_id:
        return render(request, 'attendance/scan.html', {
            'code': code, 
            'students': students,
            'message': 'Please select your name or enter ID', 
            'status': 'error'
        })

    if not session.is_open:
        return render(request, 'attendance/scan.html', {
            'code': code, 
            'students': students,
            'message': 'Session is closed', 
            'status': 'error'
        })

    # Create or get student
    student, created = Student.objects.get_or_create(
        student_id=student_id, 
        defaults={'full_name': student_id}
    )
    
    # Device fingerprint for anti-proxy
    ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or ''
    ua = request.META.get('HTTP_USER_AGENT', '')
    fingerprint = (ip + '|' + ua)[:120]
    
    try:
        AttendanceRecord.objects.create(
            session=session, 
            student=student, 
            device_fingerprint=fingerprint
        )
        message = f'✅ Attendance marked successfully for {student.full_name}'
        status = 'success'
    except Exception as e:
        message = '❌ Already scanned or same device detected'
        status = 'error'

    return render(request, 'attendance/scan.html', {
        'code': code, 
        'students': students,
        'message': message, 
        'status': status
    })


def teacher_login(request):
    if request.method == 'GET':
        return render(request, 'attendance/teacher_login.html')
    pin = request.POST.get('pin', '')
    if pin and pin == '1234':  # Fixed PIN for testing
        request.session['teacher_authed'] = True
        return redirect('dashboard')
    return render(request, 'attendance/teacher_login.html', {'error': 'Invalid PIN'})


def favicon(request):
    # Return empty 204 to avoid favicon 404 log noise during development
    return HttpResponse(status=204)


@require_http_methods(["POST"]) 
def stop_session(request, code: str):
    if request.session.get('teacher_authed') != True:
        return redirect('teacher_login')
    try:
        session = AttendanceSession.objects.get(code=code)
    except AttendanceSession.DoesNotExist:
        return redirect('home')
    session.is_active = False
    session.ends_at = min(session.ends_at, timezone.now())
    session.save(update_fields=['is_active', 'ends_at'])
    return redirect('teacher_session', code=code)
