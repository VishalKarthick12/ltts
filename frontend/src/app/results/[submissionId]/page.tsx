'use client'

import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useSubmissionResult } from '@/hooks/useApi'
import { CheckCircle, XCircle, Clock, Target, Home, RotateCcw } from 'lucide-react'
import Link from 'next/link'

export default function ResultsPage() {
  const params = useParams()
  const router = useRouter()
  const submissionId = params.submissionId as string
  
  const { data: result, isLoading } = useSubmissionResult(submissionId)

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <div>Loading results...</div>
        </div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Card className="w-full max-w-md text-center">
          <CardContent className="py-8">
            <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Results Not Found</h2>
            <p className="text-gray-600 mb-4">The test results could not be found.</p>
            <Link href="/dashboard">
              <Button>Return to Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  const percentage = result.score
  const isPassed = result.is_passed

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Results Header */}
        <Card className="mb-8 shadow-xl">
          <CardHeader className="text-center">
            <div className={`mx-auto w-20 h-20 rounded-full flex items-center justify-center mb-4 ${
              isPassed ? 'bg-green-100' : 'bg-red-100'
            }`}>
              {isPassed ? (
                <CheckCircle className="h-10 w-10 text-green-600" />
              ) : (
                <XCircle className="h-10 w-10 text-red-600" />
              )}
            </div>
            
            <CardTitle className={`text-3xl font-bold ${
              isPassed ? 'text-green-700' : 'text-red-700'
            }`}>
              {isPassed ? 'Congratulations!' : 'Test Completed'}
            </CardTitle>
            
            <CardDescription className="text-lg">
              {result.test_title}
            </CardDescription>
          </CardHeader>
          
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 text-center">
              <div className="space-y-2">
                <div className={`text-3xl font-bold ${
                  isPassed ? 'text-green-600' : 'text-red-600'
                }`}>
                  {percentage.toFixed(1)}%
                </div>
                <div className="text-sm text-gray-600">Final Score</div>
              </div>
              
              <div className="space-y-2">
                <div className="text-3xl font-bold text-blue-600">
                  {result.correct_answers}/{result.total_questions}
                </div>
                <div className="text-sm text-gray-600">Correct Answers</div>
              </div>
              
              <div className="space-y-2">
                <div className="text-3xl font-bold text-purple-600">
                  {result.time_taken_minutes || 0}
                </div>
                <div className="text-sm text-gray-600">Minutes Taken</div>
              </div>
              
              <div className="space-y-2">
                <div className={`text-3xl font-bold ${
                  isPassed ? 'text-green-600' : 'text-red-600'
                }`}>
                  {isPassed ? 'PASS' : 'FAIL'}
                </div>
                <div className="text-sm text-gray-600">
                  Threshold: {result.test_title ? '70' : '60'}%
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Detailed Results */}
        {result.question_results && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Target className="h-5 w-5" />
                <span>Question-by-Question Results</span>
              </CardTitle>
              <CardDescription>
                Review your answers and see the correct responses
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {result.question_results.map((questionResult: any, index: number) => (
                  <div key={questionResult.question_id} className={`p-4 rounded-lg border-l-4 ${
                    questionResult.is_correct 
                      ? 'bg-green-50 border-green-400' 
                      : 'bg-red-50 border-red-400'
                  }`}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900 mb-2">
                          Question {index + 1}
                        </div>
                        <div className="text-sm space-y-1">
                          <div>
                            <span className="font-medium">Your answer:</span> {questionResult.selected_answer}
                          </div>
                          <div>
                            <span className="font-medium">Correct answer:</span> {questionResult.correct_answer}
                          </div>
                        </div>
                      </div>
                      <div className={`ml-4 ${
                        questionResult.is_correct ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {questionResult.is_correct ? (
                          <CheckCircle className="h-5 w-5" />
                        ) : (
                          <XCircle className="h-5 w-5" />
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Actions */}
        <div className="flex justify-center space-x-4">
          <Link href="/dashboard">
            <Button variant="outline" className="flex items-center space-x-2">
              <Home className="h-4 w-4" />
              <span>Back to Dashboard</span>
            </Button>
          </Link>
          
          {result.test_id && (
            <Link href={`/test/${result.test_id}`}>
              <Button 
                className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 flex items-center space-x-2"
              >
                <RotateCcw className="h-4 w-4" />
                <span>Take Again</span>
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
