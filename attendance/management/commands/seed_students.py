from django.core.management.base import BaseCommand

from attendance.models import Student


class Command(BaseCommand):
    help = "Seed the database with dummy students"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=30, help="How many students to create")

    def handle(self, *args, **options):
        count = options["count"]
        created = 0
        for i in range(1, count + 1):
            student_id = f"S{i:03d}"
            full_name = f"Student {i:03d}"
            obj, was_created = Student.objects.get_or_create(
                student_id=student_id,
                defaults={"full_name": full_name, "is_active": True},
            )
            created += 1 if was_created else 0
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new students (total requested {count})."))

