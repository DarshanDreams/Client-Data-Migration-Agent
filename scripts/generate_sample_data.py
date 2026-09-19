from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


hr_data = pd.DataFrame(
    [
        {
            "Employee No": "E001",
            "First Name": " John ",
            "Last Name": "Smith",
            "Email Address": "JOHN.SMITH@EXAMPLE.COM",
            "Mobile": "+91 9876543210",
            "DOB": "15/03/1995",
            "Joined On": "2022-06-01",
            "Department": "Engineering",
        },
        {
            "Employee No": "E002",
            "First Name": "Priya",
            "Last Name": "Sharma",
            "Email Address": "priya.sharma@example.com",
            "Mobile": "+91 9876543211",
            "DOB": "1997-11-22",
            "Joined On": "01/07/2023",
            "Department": "HR",
        },
        {
            "Employee No": "E003",
            "First Name": "Rahul",
            "Last Name": "Verma",
            "Email Address": "rahul.verma@example.com",
            "Mobile": "+91 9876543212",
            "DOB": "1994-02-10",
            "Joined On": "2021-09-15",
            "Department": "Sales",
        },
    ]
)


crm_data = pd.DataFrame(
    [
        {
            "emp_id": "E001",
            "fname": "John",
            "surname": "Smith",
            "email": "john.smith@example.com",
            "phone_number": "+91 9876543210",
            "birth_date": "1995-03-15",
            "start_date": "06/01/2022",
            "dept": "engineering",
        },
        {
            "emp_id": "E002",
            "fname": "Priya",
            "surname": "Sharma",
            "email": "priya.sharma@example.com",
            "phone_number": "+91 9876543211",
            "birth_date": "22-11-1997",
            "start_date": "2023/07/01",
            "dept": "Human Resources",
        },
        {
            "emp_id": "E004",
            "fname": "Amit",
            "surname": "Patel",
            "email": "amit.patel@example.com",
            "phone_number": "+91 9876543213",
            "birth_date": "1992-05-18",
            "start_date": "2024-01-10",
            "dept": "Finance",
        },
    ]
)


hr_data.to_csv(DATA_DIR / "source_hr.csv", index=False)
crm_data.to_excel(DATA_DIR / "source_crm.xlsx", index=False)

print("Sample data generated successfully.")