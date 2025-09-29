from django.core.management.base import BaseCommand

from attendance.models import Teacher, Subject


class Command(BaseCommand):
    help = "Seed teachers and subjects"

    def handle(self, *args, **options):
        teachers = [
            "Prof. Ada Lovelace",
            "Dr. Alan Turing",
            "Dr. Grace Hopper",
        ]
        subjects = [
            "Mathematics",
            "Computer Science",
            "Physics",
        ]
        t_new = 0
        for name in teachers:
            _, created = Teacher.objects.get_or_create(full_name=name)
            t_new += 1 if created else 0
        s_new = 0
        for name in subjects:
            _, created = Subject.objects.get_or_create(name=name)
            s_new += 1 if created else 0
        self.stdout.write(self.style.SUCCESS(f"Seeded {t_new} teachers, {s_new} subjects"))

