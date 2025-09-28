'use client'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { useQuestionBanks, useCreateTest } from '@/hooks/useApi'
import { Loader2, Users, Settings, Database, Clock, Plus, Target, HelpCircle } from 'lucide-react'
import { useToast } from '@/components/ui/toast'
import { Tooltip } from '@/components/ui/tooltip'
import { motion } from 'framer-motion'

interface CreateTestFormProps {
  onSuccess?: (testId: string) => void
  onCancel?: () => void
}

export function CreateTestForm({ onSuccess, onCancel }: CreateTestFormProps) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    question_bank_ids: [] as string[],
    num_questions: 10,
    time_limit_minutes: 30,
    difficulty_filter: '',
    category_filter: '',
    is_public: false,
    max_attempts: 1,
    pass_threshold: 60
  })
  const [error, setError] = useState('')

  const createTestMutation = useCreateTest()
  const { data: questionBanks, isLoading: questionBanksLoading } = useQuestionBanks()
  const { addToast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!formData.title || formData.question_bank_ids.length === 0) {
      setError('Please fill in all required fields')
      return
    }

    try {
      // Sanitize numeric fields; ensure no NaN leaks to UI/submit
      const numQuestions = Number.isNaN(Number(formData.num_questions)) ? 1 : Math.max(1, Number(formData.num_questions))
      const timeLimit = Number.isNaN(Number(formData.time_limit_minutes)) || Number(formData.time_limit_minutes) < 1
        ? undefined
        : Number(formData.time_limit_minutes)
      const maxAttempts = Number.isNaN(Number(formData.max_attempts)) ? 1 : Math.max(1, Number(formData.max_attempts))
      const passThreshold = Number.isNaN(Number(formData.pass_threshold)) ? 60 : Math.min(100, Math.max(0, Number(formData.pass_threshold)))

      const testData: any = {
        title: formData.title,
        description: formData.description || undefined,
        question_bank_ids: formData.question_bank_ids,
        num_questions: numQuestions,
        time_limit_minutes: timeLimit,
        difficulty_filter: formData.difficulty_filter || undefined,
        category_filter: formData.category_filter || undefined,
        is_public: formData.is_public,
        max_attempts: maxAttempts,
        pass_threshold: passThreshold,
      }
      
      const result = await createTestMutation.mutateAsync(testData)
      addToast('Test created successfully! 🎉', 'success')
      onSuccess?.(result.id)
    } catch (err: any) {
      const errorMsg = err?.message || 'Failed to create test'
      setError(errorMsg)
      addToast(errorMsg, 'error')
    }
  }

  const handleChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card className="w-full max-w-2xl mx-auto shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Plus className="h-5 w-5" />
            <span>Create New Test</span>
          </CardTitle>
          <CardDescription>
            Generate a test from your question banks with custom settings
          </CardDescription>
        </CardHeader>
        <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Information */}
          <motion.div 
            className="space-y-4"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
          >
            <h3 className="text-lg font-medium text-gray-900">Basic Information</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="title">Test Title *</Label>
                <Input
                  id="title"
                  placeholder="Enter test title"
                  value={formData.title}
                  onChange={(e) => handleChange('title', e.target.value)}
                  required
                />
              </div>
              
              <div className="space-y-2">
                <Label>Question Banks *</Label>
                <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Select one or more banks to include in this test</span>
              <a
                href="/dashboard"
                className="inline-flex items-center rounded-md px-3 py-2 text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 shadow-sm transition-colors"
                title="Upload or manage question banks"
              >
                + Add Question Bank
              </a>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {questionBanks?.map((qb: any) => {
                    const checked = formData.question_bank_ids.includes(qb.id)
                    return (
                      <label key={qb.id} className={`flex items-center justify-between border rounded-md p-3 cursor-pointer hover:bg-gray-50 ${checked ? 'border-blue-300 bg-blue-50' : ''}`}>
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900">{qb.name}</div>
                          <div className="text-xs text-gray-600">{qb.question_count} questions</div>
                        </div>
                        <input
                          type="checkbox"
                          className="h-4 w-4 text-blue-600"
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              handleChange('question_bank_ids', Array.from(new Set([...formData.question_bank_ids, qb.id])))
                            } else {
                              handleChange('question_bank_ids', formData.question_bank_ids.filter(id => id !== qb.id))
                            }
                          }}
                        />
                      </label>
                    )
                  })}
                </div>
                <div className="text-xs text-gray-500">Select one or more banks. Questions will be split evenly.</div>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <textarea
                id="description"
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                placeholder="Optional test description"
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
              />
            </div>
          </motion.div>

          {/* Test Configuration */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <h3 className="text-lg font-medium text-gray-900 flex items-center space-x-2">
              <Target className="h-5 w-5" />
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <div className="flex items-center space-x-1">
                  <Label htmlFor="num_questions">Number of Questions</Label>
                  <Tooltip content="Total questions to include in the test. Questions will be distributed evenly across selected banks.">
                    <HelpCircle className="h-3 w-3 text-gray-400" />
                  </Tooltip>
                </div>
                <Input
                  id="num_questions"
                  type="number"
                  min="1"
                  max="100"
                  value={Number.isFinite(formData.num_questions) ? formData.num_questions : 0}
                  onChange={(e) => {
                    const v = e.target.value
                    const n = v === '' ? 0 : (parseInt(v, 10) || 0)
                    handleChange('num_questions', Math.max(0, n))
                  }}
                />
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center space-x-1">
                  <Label htmlFor="time_limit">Time Limit (minutes)</Label>
                  <Tooltip content="Optional time limit for the test. Leave as 0 for unlimited time.">
                    <HelpCircle className="h-3 w-3 text-gray-400" />
                  </Tooltip>
                </div>
                <Input
                  id="time_limit"
                  type="number"
                  min="1"
                  max="480"
                  placeholder="Optional"
                  value={Number.isFinite(formData.time_limit_minutes as any) ? (formData.time_limit_minutes as number) : 0}
                  onChange={(e) => {
                    const v = e.target.value
                    const n = v === '' ? 0 : (parseInt(v, 10) || 0)
                    handleChange('time_limit_minutes', Math.max(0, n))
                  }}
                />
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center space-x-1">
                  <Label htmlFor="pass_threshold">Pass Threshold (%)</Label>
                  <Tooltip content="Minimum score percentage required to pass the test.">
                    <HelpCircle className="h-3 w-3 text-gray-400" />
                  </Tooltip>
                </div>
                <Input
                  id="pass_threshold"
                  type="number"
                  min="0"
                  max="100"
                  value={Number.isFinite(formData.pass_threshold as any) ? (formData.pass_threshold as number) : 0}
                  onChange={(e) => {
                    const v = e.target.value
                    const n = v === '' ? 0 : (parseFloat(v) || 0)
                    handleChange('pass_threshold', Math.min(100, Math.max(0, n)))
                  }}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="difficulty">Difficulty Filter</Label>
                <select
                  id="difficulty"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={formData.difficulty_filter}
                  onChange={(e) => handleChange('difficulty_filter', e.target.value)}
                >
                  <option value="">All difficulties</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="max_attempts">Max Attempts</Label>
                <Input
                  id="max_attempts"
                  type="number"
                  min="1"
                  max="10"
                  value={Number.isFinite(formData.max_attempts as any) ? (formData.max_attempts as number) : 1}
                  onChange={(e) => {
                    const v = e.target.value
                    const n = v === '' ? 1 : (parseInt(v, 10) || 1)
                    handleChange('max_attempts', Math.max(1, n))
                  }}
                />
              </div>
            </div>
          </motion.div>

          {/* Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-gray-900 flex items-center space-x-2">
              <Users className="h-5 w-5" />
              <span>Access Settings</span>
            </h3>
            
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="is_public"
                checked={formData.is_public}
                onChange={(e) => handleChange('is_public', e.target.checked)}
                className="rounded border-gray-300"
              />
              <Label htmlFor="is_public">Make test publicly accessible</Label>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex space-x-3">
            <Button
              type="submit"
              className="flex-1 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
              disabled={createTestMutation.isPending || questionBanksLoading}
            >
              {createTestMutation.isPending ? 'Creating Test...' : 'Create Test'}
            </Button>
            
            {onCancel && (
              <Button
                type="button"
                variant="outline"
                onClick={onCancel}
                disabled={createTestMutation.isPending}
              >
                Cancel
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
    </motion.div>
  )
}
