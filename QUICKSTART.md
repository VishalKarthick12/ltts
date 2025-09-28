# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Run Setup Script
```powershell
# In PowerShell (Windows)
./setup.ps1

# Or manually:
cd frontend && npm install
cd ../backend && pip install -r requirements.txt
```

### 2. Configure Supabase
1. Create account at [supabase.com](https://supabase.com)
2. Create new project
3. Copy credentials to environment files:
   - `frontend/.env.local`
   - `backend/.env`

### 3. Setup Database
Copy and run SQL from `docs/database-schema.md` in Supabase SQL Editor

### 4. Start Servers
```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload

# Terminal 2 - Frontend  
cd frontend
npm run dev
```

### 5. Test Application
- Visit: http://localhost:3000
- Backend API: http://localhost:8000/api/health
- Should see login page and working backend status

## 🔧 Environment Variables

### Frontend (.env.local)
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=your-database-url
ENVIRONMENT=development
```

## ✅ What's Included

- **Authentication**: Supabase Auth with login page
- **Dashboard**: Admin interface with backend status
- **API**: FastAPI with health endpoint
- **Database**: PostgreSQL schema ready for questions
- **Frontend**: Next.js 15 + Tailwind + shadcn/ui
- **State Management**: React Query integration
- **File Upload UI**: Ready for Excel/CSV processing

## 🛠️ Ready for Extension

The scaffolding is complete and ready for you to add:
- File upload processing
- Question parsing (Excel/CSV)
- Advanced dashboard features
- User management
- Question bank management

## 📚 Documentation

- `README.md` - Complete project overview
- `docs/database-schema.md` - Database design
- API docs available at: http://localhost:8000/docs (when backend is running)
