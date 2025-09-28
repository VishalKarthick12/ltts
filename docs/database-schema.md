# Database Schema

This document outlines the database schema for the Question Bank Management System using Supabase PostgreSQL.

## Tables

### 1. question_banks

Stores information about uploaded question bank files.

```sql
CREATE TABLE question_banks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  file_path VARCHAR(500) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
);
```

**Columns:**
- `id`: Unique identifier for the question bank
- `name`: Display name of the question bank
- `description`: Optional description
- `file_path`: Path to the uploaded file in Supabase Storage
- `created_at`: Timestamp when the record was created
- `updated_at`: Timestamp when the record was last updated
- `created_by`: Reference to the user who uploaded the question bank

### 2. questions

Stores individual questions extracted from question bank files.

```sql
CREATE TABLE questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question_bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
  question_text TEXT NOT NULL,
  question_type VARCHAR(50) NOT NULL CHECK (question_type IN ('multiple_choice', 'true_false', 'short_answer', 'essay')),
  options TEXT[], -- Array of options for multiple choice questions
  correct_answer TEXT NOT NULL,
  difficulty_level VARCHAR(20) CHECK (difficulty_level IN ('easy', 'medium', 'hard')),
  category VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Columns:**
- `id`: Unique identifier for the question
- `question_bank_id`: Reference to the parent question bank
- `question_text`: The actual question text
- `question_type`: Type of question (multiple_choice, true_false, etc.)
- `options`: Array of options for multiple choice questions
- `correct_answer`: The correct answer
- `difficulty_level`: Optional difficulty classification
- `category`: Optional category/subject classification
- `created_at`: Timestamp when the question was added

## Indexes

```sql
-- Improve query performance
CREATE INDEX idx_questions_question_bank_id ON questions(question_bank_id);
CREATE INDEX idx_questions_category ON questions(category);
CREATE INDEX idx_questions_difficulty ON questions(difficulty_level);
CREATE INDEX idx_question_banks_created_by ON question_banks(created_by);
```

## Row Level Security (RLS)

Enable RLS on both tables to ensure users can only access their own data:

```sql
-- Enable RLS
ALTER TABLE question_banks ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;

-- Policies for question_banks
CREATE POLICY "Users can view own question banks" ON question_banks
  FOR SELECT USING (auth.uid() = created_by);

CREATE POLICY "Users can insert own question banks" ON question_banks
  FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Users can update own question banks" ON question_banks
  FOR UPDATE USING (auth.uid() = created_by);

CREATE POLICY "Users can delete own question banks" ON question_banks
  FOR DELETE USING (auth.uid() = created_by);

-- Policies for questions
CREATE POLICY "Users can view questions from own question banks" ON questions
  FOR SELECT USING (
    auth.uid() IN (
      SELECT created_by FROM question_banks 
      WHERE id = questions.question_bank_id
    )
  );

CREATE POLICY "Users can insert questions to own question banks" ON questions
  FOR INSERT WITH CHECK (
    auth.uid() IN (
      SELECT created_by FROM question_banks 
      WHERE id = questions.question_bank_id
    )
  );
```

## Storage Buckets

Create a storage bucket for uploaded files:

```sql
-- Create storage bucket for question bank files
INSERT INTO storage.buckets (id, name, public) 
VALUES ('question-banks', 'question-banks', false);

-- Create policy for the bucket
CREATE POLICY "Users can upload own files" ON storage.objects
  FOR INSERT WITH CHECK (bucket_id = 'question-banks' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can view own files" ON storage.objects
  FOR SELECT USING (bucket_id = 'question-banks' AND auth.uid()::text = (storage.foldername(name))[1]);
```

## Setup Instructions

1. Run the SQL commands above in your Supabase SQL editor
2. Ensure RLS policies are properly configured
3. Create the storage bucket for file uploads
4. Update your application's TypeScript types to match the schema

