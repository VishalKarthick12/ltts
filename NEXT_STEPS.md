# Next Steps: Building Core Question Bank Features

## 🚀 Current Status
✅ Backend structure created with proper modules  
✅ Database connection utilities implemented  
✅ Pydantic models for all data structures  
✅ FastAPI endpoints for question bank management  
✅ Excel/CSV file processing service  
✅ Comprehensive error handling and validation  

## 📋 Step-by-Step Implementation Guide

### Step 1: Install New Dependencies and Test Connection

```bash
# In your backend directory (with venv activated)
cd backend
pip install -r requirements.txt

# Test database connection
python test_connection.py
```

**Expected Output:** ✅ PostgreSQL and Supabase connections successful

### Step 2: Set Up Database Schema

```bash
# Run the database setup script
python setup_database.py
```

**What this does:**
- Creates `question_banks`, `questions`, `tests`, and `test_submissions` tables
- Sets up indexes for performance
- Adds triggers for automatic timestamp updates
- Optionally configures Row Level Security

### Step 3: Start and Test the Enhanced Backend

```bash
# Start FastAPI server
uvicorn app.main:app --reload
```

**Test these endpoints:**
- `GET http://localhost:8000/api/health` - Should show database status
- `GET http://localhost:8000/docs` - Interactive API documentation
- `GET http://localhost:8000/api/question-banks/` - Empty list initially

### Step 4: Test File Upload (Create Sample Excel File)

Create a test Excel file with these columns:
```
| question | type | options | correct_answer | difficulty | category |
|----------|------|---------|----------------|------------|----------|
| What is 2+2? | multiple_choice | 2|3|4|5 | 4 | easy | math |
| Python is a programming language | true_false | | True | easy | programming |
```

Save as `sample_questions.xlsx` and test upload:
```bash
curl -X POST "http://localhost:8000/api/question-banks/upload" \
  -F "file=@sample_questions.xlsx" \
  -F "name=Sample Question Bank" \
  -F "description=Test upload"
```

### Step 5: Update Frontend to Use New Endpoints

Update `frontend/src/lib/api.ts` to match the new backend structure:

```typescript
// Add these new API methods
export const api = {
  // Existing methods...
  
  // Enhanced question bank methods
  getQuestionBankDetails: (id: string) => 
    apiRequest<QuestionBankResponse>(`/api/question-banks/${id}`),
  
  getQuestionsByBank: (id: string, filters?: {
    category?: string;
    difficulty?: string;
    skip?: number;
    limit?: number;
  }) => {
    const params = new URLSearchParams();
    if (filters?.category) params.append('category', filters.category);
    if (filters?.difficulty) params.append('difficulty', filters.difficulty);
    if (filters?.skip) params.append('skip', filters.skip.toString());
    if (filters?.limit) params.append('limit', filters.limit.toString());
    
    return apiRequest<QuestionResponse[]>(`/api/question-banks/${id}/questions?${params}`);
  },
  
  deleteQuestionBank: (id: string) =>
    apiRequest(`/api/question-banks/${id}`, { method: 'DELETE' }),
}
```

### Step 6: Enhance Dashboard with Real Data

Update `frontend/src/app/dashboard/page.tsx` to fetch and display real question banks:

```typescript
import { useQuestionBanks } from '@/hooks/useApi'

// In your component:
const { data: questionBanks, isLoading, error } = useQuestionBanks()

// Display actual counts instead of hardcoded zeros
const totalQuestionBanks = questionBanks?.length || 0
const totalQuestions = questionBanks?.reduce((sum, qb) => sum + (qb.question_count || 0), 0) || 0
```

### Step 7: Implement File Upload Functionality

Update the dashboard's upload button to actually upload files:

```typescript
const { mutate: uploadFile, isLoading: uploading } = useUploadQuestionBank()

const handleUploadQuestionBank = async (file: File) => {
  uploadFile(
    { 
      file, 
      metadata: { 
        name: file.name.replace(/\.[^/.]+$/, ""), 
        description: "Uploaded via dashboard" 
      } 
    },
    {
      onSuccess: (data) => {
        console.log('Upload successful:', data)
        // Show success message
      },
      onError: (error) => {
        console.error('Upload failed:', error)
        // Show error message
      }
    }
  )
}
```

## 🔧 Project Structure (Current)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app with all routes
│   ├── database.py          # Database connection utilities
│   ├── models.py            # Pydantic schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   └── question_banks.py # Question bank endpoints
│   └── services/
│       ├── __init__.py
│       └── file_processor.py # Excel/CSV processing
├── test_connection.py       # Database connection test
├── setup_database.py       # Database schema setup
├── requirements.txt         # Updated dependencies
└── .env                     # Your Supabase credentials
```

## 🎯 Next Features to Build

### Phase 1: Core Functionality (Current)
- [x] Question bank upload and management
- [x] File processing (Excel/CSV)
- [x] Database schema and connections
- [x] Basic CRUD operations

### Phase 2: Test Generation (Next)
- [ ] Create test generation endpoints
- [ ] Build test-taking interface
- [ ] Implement answer submission
- [ ] Score calculation and results

### Phase 3: Advanced Features
- [ ] User authentication integration
- [ ] Test scheduling and time limits
- [ ] Result analytics and reporting
- [ ] Export functionality

## 🚨 Common Issues and Solutions

### Database Connection Issues
```bash
# Check your .env file has correct DATABASE_URL
# Format: postgresql://postgres:[password]@[host]:[port]/postgres?sslmode=require

# Test connection manually
python test_connection.py
```

### File Upload Issues
- Ensure file size < 10MB
- Supported formats: .xlsx, .xls, .csv
- Required columns: question, correct_answer
- Optional columns: type, options, difficulty, category

### CORS Issues
- Backend allows localhost:3000 by default
- Update CORS origins in `app/main.py` if needed

## 📚 API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation with:
- All endpoints documented
- Request/response schemas
- Try-it-out functionality
- Authentication requirements

## 🔄 Development Workflow

1. **Backend First**: Implement and test API endpoints
2. **Database**: Ensure schema changes are applied
3. **Frontend Integration**: Update API calls and UI
4. **Testing**: Use both unit tests and manual testing
5. **Error Handling**: Implement proper error states in UI

## 📝 Cursor-Compatible Commands

```bash
# Terminal commands to run in sequence:
cd backend
python test_connection.py
python setup_database.py
uvicorn app.main:app --reload

# In another terminal:
cd frontend  
npm run dev

# Test endpoints:
curl http://localhost:8000/api/health
curl http://localhost:8000/api/question-banks/
```

This setup gives you a solid foundation for building out the complete question bank management system. The architecture is scalable and follows FastAPI best practices!
