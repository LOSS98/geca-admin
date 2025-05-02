# GECA Admin Dashboard

A Flask-based administrative web application developed for "Los Barryachis" BDE (Bureau Des Étudiants) 2025 campaign at INSA Hauts-de-France. This platform serves as the central management system for the campaign team to coordinate activities, manage tasks, and organize events.

![Los Barryachis Logo](https://scontent-cdg4-3.cdninstagram.com/v/t51.2885-19/491443873_17848131525452154_2583769738917651108_n.jpg?_nc_ht=scontent-cdg4-3.cdninstagram.com&_nc_cat=106&_nc_oc=Q6cZ2QG4CVqPzfV1DzJF5oCLGq4HvocS8XBN9oZTRhu0tbISAAFDJBngTiVOWIQFvoCyLj__4PIGJVi0hhPwhEzLSi4t&_nc_ohc=21sl6x6OeLkQ7kNvwHahG2s&_nc_gid=MDGrUDS7t4tI2rNqSQ1V4w&edm=AP4sbd4BAAAA&ccb=7-5&oh=00_AfGFxmP2FHsSV1T8AvgEdp1j5g3mh_r5V2MbHM5zYlncBw&oe=681A60AA&_nc_sid=7a9f4b)

## 📋 Overview

GECA Admin Dashboard was created specifically for the Los Barryachis BDE 2025 campaign as an internal management tool. It provides a centralized platform for campaign team members to coordinate their efforts, manage resources, and track progress across various campaign activities.

The dashboard serves as the backbone of the campaign's operations, helping with:

- Internal task management and delegation among different teams (Communications, Treasury, Events, etc.)
- Financial tracking for campaign expenses and income
- Scheduling and managing campaign events through the "shotgun" registration system
- Publishing and updating communication materials and designs
- Coordinating team members during events with location tracking
- Monitoring campaign KPIs and statistics

The application uses Google authentication for user management and integrates with Google services (Sheets, Drive) for data storage and retrieval, ensuring that all campaign-related information is securely stored and easily accessible to team members with appropriate permissions.

## 🔧 Tech Stack

- **Backend**: Python 3.9 with Flask
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQL (SQLAlchemy ORM)
- **Authentication**: Google OAuth
- **Containerization**: Docker
- **Deployment**: Gunicorn with Gevent

## 🚀 Installation

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (optional)
- Google API credentials

### Environment Setup

1. Clone the repository
```bash
git clone https://github.com/your-username/geca-admin.git
cd geca-admin
```

2. Create a virtual environment and install dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:
```
SECRET_KEY=your_secret_key
DB_URI=your_database_uri
WHATSAPP_API_URL=your_whatsapp_api_url
WHATSAPP_API_KEY=your_whatsapp_api_key
EXPENSE_SCRIPT_ID=your_google_script_id
INCOME_SCRIPT_ID=your_google_script_id
GENERAL_SCRIPT_ID=your_google_script_id
FILES_DIR=/path/to/files_directory
FILES_API_URL=your_files_api_url
FILES_API_KEY=your_files_api_key
MAINTENANCE=0
```

4. Place your Google OAuth credentials in `credentials.json` (required for authentication)

### Running with Docker

Build and run the application using Docker Compose:
```bash
docker-compose up -d
```

### Running Locally

Start the application using Flask development server:
```bash
python main.py
```

Or with Gunicorn:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 5 --worker-class gevent --worker-connections 1000 --timeout 300 --log-level info wsgi:app
```

## 📁 Project Structure

```
geca-admin/
├── __init__.py           # Package initialization
├── main.py               # Application entry point
├── wsgi.py               # WSGI entry point for production
├── config.py             # Configuration settings
├── db.py                 # Database initialization
├── models/               # Database models
│   ├── user.py           # User model and authentication
│   ├── role.py           # Roles and permissions
│   ├── task.py           # Task management
│   ├── expense.py        # Financial expense tracking
│   ├── income.py         # Financial income tracking
│   └── ...               # Other models
├── routes/               # Application routes/controllers
│   ├── auth.py           # Authentication routes
│   ├── tasks.py          # Task management routes
│   ├── finances.py       # Financial management routes
│   ├── locations.py      # User location tracking
│   └── ...               # Other route modules
├── services/             # External service integrations
│   ├── google_api.py     # Google API integration
│   ├── notifications.py  # Notification service
│   └── ...               # Other services
├── templates/            # Jinja2 HTML templates
├── static/               # Static assets (CSS, JS, images)
└── docker-compose.yml    # Docker Compose configuration
```

## 🔍 Features

### Task Management

- Create, assign, and track tasks across different campaign teams
- Task prioritization (high, medium, low) to focus on critical campaign activities
- Task states (assigned, disputed, to be validated, done) for complete workflow management
- Task assignment by individual team member or by team role (Communications, Treasury, Events)
- Comments on tasks for team communication and coordination
- Task history for campaign activity auditing and accountability

### Financial Management

- Record all campaign income and expenses with detailed categorization
- Internal transfers between campaign accounts and team budgets
- Integration with Google Sheets for transparent financial reporting to all team members
- Expense approval workflow for budget control

### User Management

- Google-based authentication for secure access by campaign team members
- Team role assignments based on campaign structure (Communications, Treasury, etc.)
- User location tracking during events for real-time team coordination
- Member management interface for onboarding new campaign volunteers

### Shotgun Management (Event Registration)

- Create and manage registrations for campaign events ("shotguns")
- Track participant information for event planning and follow-up
- Excel import for batch participant registration from preliminary sign-up sheets
- Image upload for event promotion materials and campaign visuals

### Communications Management

- Central repository for campaign designs and promotional materials
- Tracking of content publication status and approvals
- Management of design requests across different campaign initiatives

### Statistics Dashboard

- Configurable statistics dashboard for campaign KPIs
- Real-time counters with increment/decrement for event metrics
- Customizable display order for focusing on priority campaign metrics

### Maps and Location

- Real-time campaign team location tracking during events
- Visual representation on interactive map for coordination
- Location timestamp indicators to facilitate team deployment during campaign activities

## 🔐 Authentication

The application uses Google OAuth for authentication. Users must have a valid Google account to access the system. User permissions are based on assigned roles.

## 📱 Notification System

Notifications are sent via a WhatsApp integration for various events:
- Task assignments and updates
- Financial transactions
- User status changes

## 🧩 API Endpoints

The application provides various API endpoints for frontend interactions, including:

- `/api/tasks` - Task management
- `/api/users` - User management
- `/api/statistics` - Statistics management
- `/api/members-management` - Member management
- `/api/files` - File management
- `/api/users-locations` - User location tracking

## 🔄 Database Models

Key models include:
- User - User information and authentication
- Role - User roles and permissions
- Task - Task management and assignment
- Expense/Income - Financial tracking
- Shotgun/ShotgunParticipant - Event registration
- Statistic - Configurable statistics

## ⚠️ Maintenance Mode

The application includes a maintenance mode feature that can be enabled by setting the `MAINTENANCE` environment variable to `1`. This displays a maintenance banner and restricts certain operations.


This project was developed for Los Barryachis BDE 2025 campaign at INSA Hauts-de-France. The application serves as our internal management system, coordinating everything from team task assignments and treasury management to promotional material publication and event organization.
- Khalil MZOUGHI
