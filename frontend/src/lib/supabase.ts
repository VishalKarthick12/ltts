import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Database types (will be generated from Supabase CLI)
export type Database = {
  public: {
    Tables: {
      question_banks: {
        Row: {
          id: string;
          name: string;
          description: string | null;
          file_path: string;
          created_at: string;
          updated_at: string;
          created_by: string;
        };
        Insert: {
          id?: string;
          name: string;
          description?: string | null;
          file_path: string;
          created_at?: string;
          updated_at?: string;
          created_by: string;
        };
        Update: {
          id?: string;
          name?: string;
          description?: string | null;
          file_path?: string;
          created_at?: string;
          updated_at?: string;
          created_by?: string;
        };
      };
      questions: {
        Row: {
          id: string;
          question_bank_id: string;
          question_text: string;
          question_type: string;
          options: string[] | null;
          correct_answer: string;
          difficulty_level: string | null;
          category: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          question_bank_id: string;
          question_text: string;
          question_type: string;
          options?: string[] | null;
          correct_answer: string;
          difficulty_level?: string | null;
          category?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          question_bank_id?: string;
          question_text?: string;
          question_type?: string;
          options?: string[] | null;
          correct_answer?: string;
          difficulty_level?: string | null;
          category?: string | null;
          created_at?: string;
        };
      };
    };
  };
};

