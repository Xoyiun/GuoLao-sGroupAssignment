from data_manager import DataManager

class F1Manager(DataManager):

    def __init__(self, json_path="04_data_format.json"):
        # Inherit initialization and JSON loading from DataManager (F6 feature)
        super().__init__(json_path)

    # ==========================================
    # F1 Core Management & Validation Functions
    # ==========================================

    def add_classroom(self, room_id, capacity, equipment):
        """Add a classroom with capacity checks"""
        for r in self.get_classrooms():
            if r["room_id"] == room_id:
                return False, "Error: Classroom ID already exists."
        if capacity < 1:
            return False, "Error: Classroom capacity must be at least 1."

        new_room = {
            "room_id": room_id,
            "capacity": capacity,
            "equipment": equipment,
        }
        self.data["classrooms"].append(new_room)
        self.save()
        return True, f"Classroom {room_id} added successfully."

    def add_course(
        self,
        course_id,
        name,
        credits,
        type_req,
        teacher,
        capacity,
        room,
        time_slots,
    ):
        """Add a course with F1 complete validation rules and auto-save"""
        # 1. Check for duplicate course ID
        for c in self.get_courses():
            if c.get("course_id") == course_id or c.get("id") == course_id:
                return False, "Error: Course ID already exists."

        # 2. Verify credits are a positive integer
        if not isinstance(credits, int) or credits <= 0:
            return False, "Error: Credits must be a positive integer."

        # 3. Verify capacity is valid
        if capacity < 1:
            return False, "Error: Course capacity must be at least 1."

        # 4. Verify classroom exists and fits capacity
        room_obj = next(
            (r for r in self.get_classrooms() if r["room_id"] == room), None
        )
        if not room_obj:
            return False, "Error: Classroom does not exist."
        if capacity > room_obj["capacity"]:
            return False, "Error: Course capacity exceeds classroom capacity."

        # 5. Construct course structure
        new_course = {
            "course_id": course_id,
            "name": name,
            "credits": credits,
            "type": type_req,
            "teacher": teacher,
            "capacity": capacity,
            "room": room,
            "schedule": time_slots,
            "enrolled_students": [],
        }

        self.data["courses"].append(new_course)
        self.save()  # Auto-save to JSON
        return True, f"Course {course_id} added successfully."

    def delete_course(self, course_id):
        """Delete a course with deletion constraints (cannot delete if students are enrolled)"""
        course = next(
            (
                c
                for c in self.get_courses()
                if c.get("course_id") == course_id or c.get("id") == course_id
            ),
            None,
        )
        if not course:
            return False, "Error: Course not found."

        # Constraint: Cannot delete if active students are enrolled
        if len(course.get("enrolled_students", [])) > 0:
            return False, (
                "Error: Cannot delete course with active student enrollments."
            )

        self.data["courses"].remove(course)
        self.save()
        return True, f"Course {course_id} deleted successfully."

    def add_student(self, student_id, name, department, max_credits):
        """Add a student with validation"""
        for s in self.get_students():
            if s.get("student_id") == student_id or s.get("id") == student_id:
                return False, "Error: Student ID already exists."
        if max_credits <= 0:
            return False, "Error: Max credits must be a positive integer."

        new_student = {
            "student_id": student_id,
            "name": name,
            "Department": department,
            "Credit_Limit": max_credits,
            "enrolled_courses": [],
        }
        self.data["students"].append(new_student)
        self.save()
        return True, f"Student {student_id} added successfully."

    def query_courses(
        self,
        teacher=None,
        day=None,
        course_type=None,
        available_only=False,
    ):
        """Multi-criteria course query (by teacher, day, type, or remaining capacity)"""
        results = []
        for c in self.get_courses():
            if teacher and c.get("teacher") != teacher:
                continue
            if course_type and c.get("type") != course_type:
                continue
            if day and not any(
                str(slot).startswith(str(day)) for slot in c.get("schedule", [])
            ):
                continue
            if available_only:
                remaining = c.get("capacity", 0) - len(
                    c.get("enrolled_students", [])
                )
                if remaining <= 0:
                    continue
            results.append(c)
        return results

    def update_student_courses(self, student_id, new_course_list):
        """Update a student's enrolled courses list and auto-save (F1, F2)"""
        for student in self.data.get("students", []):
            if (
                student.get("student_id") == student_id
                or student.get("id") == student_id
            ):
                student["enrolled_courses"] = new_course_list
                self.save()
                return True
        return False


# --- Local Test Block ---
if __name__ == "__main__":
    manager = F1Manager()
    print(manager.add_classroom("6TB-327", 100, ["projector"]))
    print(
        manager.add_course(
            "CS101",
            "Computer Programming",
            3,
            "Required",
            "Professor Wang",
            50,
            "6TB-327",
            ["1-3", "1-4"],
        )
    )
    print(manager.add_student("S001", "Wang Xiao-Ming", "CS Dept", 24))
    print(
        "Search courses by Professor Wang:",
        manager.query_courses(teacher="Professor Wang"),
    )