'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { 
  useTestDetails, useSharedTest, useStartTestSession, useTestQuestions, 
  useSessionStatus, useSaveAnswer, useSubmitTestSession,
  useCurrentUser
} from '@/hooks/useApi'
import { Clock, ChevronLeft, ChevronRight, Send, AlertCircle } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { motion } from 'framer-motion'

export default function TestTakingPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const testId = params.testId as string
  const shareToken = searchParams?.get('token') || ''
  const urlName = searchParams?.get('name') || ''
  const urlEmail = searchParams?.get('email') || ''
  
  const [sessionToken, setSessionToken] = useState<string | null>(null)
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null)
  const [showStartForm, setShowStartForm] = useState(true)
  const [participantName, setParticipantName] = useState('')
  const [participantEmail, setParticipantEmail] = useState('')
  const [timeUpOpen, setTimeUpOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // API hooks
  const { data: testDetails, isError: testDetailsError } = useTestDetails(testId)
  const { data: sharedTest, isError: sharedTestError } = useSharedTest(shareToken || null)
  const { data: user } = useCurrentUser()
  const startSessionMutation = useStartTestSession()
  const { data: questions, isLoading: questionsLoading, isError: questionsError, error: questionsErrorObj, refetch: refetchQuestions } = useTestQuestions(testId, sessionToken || '')
  const { data: sessionStatus } = useSessionStatus(sessionToken || '')
  const saveAnswerMutation = useSaveAnswer()
  const submitTestMutation = useSubmitTestSession()

  // Build a unified display object from either testDetails or sharedTest
  const display = testDetails || (sharedTest ? {
    title: sharedTest.title,
    description: sharedTest.description,
    total_questions: sharedTest.num_questions,
    time_limit_minutes: sharedTest.time_limit_minutes,
    pass_threshold: sharedTest.pass_threshold,
    max_attempts: 1,
    user_attempts: 0,
    user_best_score: null
  } : null)

  // Debug logging
  useEffect(() => {
    console.log('Test Taking Debug:', {
      testId,
      sessionToken,
      hasTestDetails: !!testDetails,
      hasSharedTest: !!sharedTest,
      hasQuestions: !!questions,
      questionsLength: questions?.length,
      showStartForm,
      shareToken
    })
  }, [testId, sessionToken, testDetails, sharedTest, questions, showStartForm, shareToken])

  // Auto-fill user info if logged in or from URL
  useEffect(() => {
    if (urlName && !participantName) {
      setParticipantName(urlName)
      setParticipantEmail(urlEmail)
    } else if (user && !participantName) {
      setParticipantName(user.name || '')
      setParticipantEmail(user.email || '')
    }
  }, [user, participantName, urlName, urlEmail])

  // Timer countdown
  useEffect(() => {
    if (sessionStatus?.minutes_remaining !== undefined && sessionStatus.minutes_remaining !== null) {
      const minutesRemaining = Number(sessionStatus.minutes_remaining)
      if (!isNaN(minutesRemaining) && isFinite(minutesRemaining)) {
        const secs = Math.max(0, Math.ceil(minutesRemaining * 60))
        setTimeRemaining(secs)
      }
    }
  }, [sessionStatus])

  useEffect(() => {
    if (timeRemaining === null || timeRemaining <= 0) return

    const timer = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev === null || prev <= 1) {
          // Time's up - auto submit
          if (sessionToken) {
            handleSubmitTest({ auto: true })
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [timeRemaining, sessionToken])

  const formatTime = (seconds: number) => {
    if (!isFinite(seconds) || isNaN(seconds) || seconds < 0) {
      return '0:00'
    }
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const handleStartTest = async () => {
    if (!participantName.trim()) {
      alert('Please enter your name')
      return
    }

    try {
      const session = await startSessionMutation.mutateAsync({
        testId,
        sessionData: {
          participant_name: participantName,
          participant_email: participantEmail || undefined,
          invite_token: shareToken || undefined
        }
      })
      
      setSessionToken(session.session_token)
      setShowStartForm(false)
    } catch (error: any) {
      alert(error.message || 'Failed to start test')
    }
  }

  const handleAnswerChange = (questionId: string, answer: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }))
    
    // Auto-save answer
    if (sessionToken) {
      saveAnswerMutation.mutate({
        sessionToken,
        answerData: {
          question_id: questionId,
          selected_answer: answer,
          question_number: currentQuestionIndex + 1
        }
      })
    }
  }

  const handleSubmitTest = async (opts?: { auto?: boolean }) => {
    if (!sessionToken) return
    if (submitting) return

    if (!opts?.auto) {
      const confirmed = window.confirm('Are you sure you want to submit your test? You cannot change your answers after submission.')
      if (!confirmed) return
    }

    try {
      if (opts?.auto) {
        setTimeUpOpen(true)
      }
      setSubmitting(true)
      const result = await submitTestMutation.mutateAsync(sessionToken)
      
      // Redirect based on whether it's a public test or authenticated user
      if (shareToken || (!user && participantEmail)) {
        // Public test - redirect to email-based results
        router.push(`/results/test/${testId}?email=${encodeURIComponent(participantEmail)}`)
      } else {
        // Authenticated user - redirect to submission-based results
        router.push(`/results/${result.id}`)
      }
    } catch (error: any) {
      alert(error.message || 'Failed to submit test')
    } finally {
      setSubmitting(false)
    }
  }

  const currentQuestion = questions?.[currentQuestionIndex]
  const isLastQuestion = currentQuestionIndex === (questions?.length || 1) - 1
  const canSubmit = questions?.every(q => answers[q.id]) || false

  if (!display && !(testDetailsError || sharedTestError)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <div>Loading test...</div>
        </div>
      </div>
    )
  }

  if (!display && (testDetailsError || sharedTestError)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-3">
          <div className="text-red-600">Failed to load test details.</div>
          {shareToken && <div className="text-sm text-gray-600">Your share link may be invalid or expired.</div>}
        </div>
      </div>
    )
  }

  if (showStartForm) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-cyan-50">
        <Card className="w-full max-w-md shadow-xl">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-gray-900">
              {display?.title}
            </CardTitle>
            <CardDescription>
              {display?.description || 'Ready to start your test?'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-blue-50 p-4 rounded-lg space-y-2">
              <div className="flex justify-between text-sm">
                <span>Questions:</span>
                <span className="font-medium">{display?.total_questions}</span>
              </div>
              {display?.time_limit_minutes && (
                <div className="flex justify-between text-sm">
                  <span>Time Limit:</span>
                  <span className="font-medium">{display.time_limit_minutes} minutes</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span>Pass Threshold:</span>
                <span className="font-medium">{display?.pass_threshold}%</span>
              </div>
              {Array.isArray((testDetails as any)?.question_bank_names) && (testDetails as any).question_bank_names.length > 0 && (
                <div className="text-xs text-gray-700">
                  <span className="font-medium">Included Banks:</span> {(testDetails as any).question_bank_names.join(', ')}
                </div>
              )}
            </div>

            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="name">Your Name *</Label>
                <Input
                  id="name"
                  value={participantName}
                  onChange={(e) => setParticipantName(e.target.value)}
                  placeholder="Enter your full name"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email (Optional)</Label>
                <Input
                  id="email"
                  type="email"
                  value={participantEmail}
                  onChange={(e) => setParticipantEmail(e.target.value)}
                  placeholder="Enter your email"
                />
              </div>
            </div>

            {testDetails && testDetails.user_attempts > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 p-3 rounded-lg">
                <div className="flex items-center space-x-2">
                  <AlertCircle className="h-4 w-4 text-yellow-600" />
                  <span className="text-sm text-yellow-800">
                    You have already attempted this test {testDetails.user_attempts} time(s).
                    {testDetails.user_best_score && ` Best score: ${testDetails.user_best_score.toFixed(1)}%`}
                  </span>
                </div>
              </div>
            )}

            <Button
              onClick={handleStartTest}
              className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
              disabled={startSessionMutation.isPending || !participantName.trim()}
            >
              {startSessionMutation.isPending ? 'Starting Test...' : 'Start Test'}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (questionsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <div>Loading questions...</div>
        </div>
      </div>
    )
  }

  if (questionsError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-4">
          <div className="text-red-600">Failed to load questions.</div>
          <div className="text-sm text-gray-600">{(questionsErrorObj as any)?.message || 'An unexpected error occurred.'}</div>
          <Button onClick={() => refetchQuestions()} className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700">Retry</Button>
        </div>
      </div>
    )
  }

  if (!questions || questions.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-2">
          <div>No questions available for this test.</div>
          <div className="text-sm text-gray-600">Please contact the test administrator.</div>
        </div>
      </div>
    )
  }

  return (
    <>
    <div className="min-h-screen bg-gray-50">
      {/* Header with timer */}
      <div className="bg-white shadow-sm border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">{display?.title}</h1>
              <p className="text-sm text-gray-600">
                Question {currentQuestionIndex + 1} of {questions.length}
              </p>
            </div>
            
            {timeRemaining !== null && (
              <div className={`flex items-center space-x-2 px-3 py-2 rounded-lg ${
                timeRemaining < 300 ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
              }`}>
                <Clock className="h-4 w-4" />
                <span className="font-mono font-medium">
                  {formatTime(timeRemaining)}
                </span>
              </div>
            )}
          </div>
          
          {/* Progress bar */}
          <div className="mt-4">
            <div className="bg-gray-200 rounded-full h-2">
              <div 
                className="bg-gradient-to-r from-blue-600 to-cyan-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Question content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">
              {currentQuestion?.question_text}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {currentQuestion?.question_type === 'multiple_choice' && currentQuestion.options ? (
                currentQuestion.options.map((option: string, index: number) => (
                  <motion.label 
                    key={index} 
                    className={`
                      flex items-center space-x-3 p-4 border-2 rounded-xl cursor-pointer transition-all duration-200
                      ${answers[currentQuestion.id] === option 
                        ? 'border-blue-500 bg-blue-50 shadow-md' 
                        : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                      }
                    `}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <input
                      type="radio"
                      name={`question-${currentQuestion.id}`}
                      value={option}
                      checked={answers[currentQuestion.id] === option}
                      onChange={(e) => handleAnswerChange(currentQuestion.id, e.target.value)}
                      className="text-blue-600 scale-125"
                    />
                    <span className="flex-1 text-gray-800">{option}</span>
                  </motion.label>
                ))
              ) : currentQuestion?.question_type === 'true_false' ? (
                ['True', 'False'].map((option: string, index: number) => (
                  <motion.label 
                    key={option} 
                    className={`
                      flex items-center space-x-3 p-4 border-2 rounded-xl cursor-pointer transition-all duration-200
                      ${answers[currentQuestion.id] === option 
                        ? 'border-green-500 bg-green-50 shadow-md' 
                        : 'border-gray-200 hover:border-green-300 hover:bg-gray-50'
                      }
                    `}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.15 }}
                  >
                    <input
                      type="radio"
                      name={`question-${currentQuestion.id}`}
                      value={option}
                      checked={answers[currentQuestion.id] === option}
                      onChange={(e) => handleAnswerChange(currentQuestion.id, e.target.value)}
                      className="text-green-600 scale-125"
                    />
                    <span className="flex-1 text-gray-800 font-medium">{option}</span>
                  </motion.label>
                ))
              ) : (
                <div className="space-y-2">
                  <Label htmlFor={`answer-${currentQuestion?.id}`}>Your Answer:</Label>
                  <textarea
                    id={`answer-${currentQuestion?.id}`}
                    className="w-full min-h-[100px] p-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="Type your answer here..."
                    value={answers[currentQuestion?.id || ''] || ''}
                    onChange={(e) => handleAnswerChange(currentQuestion?.id || '', e.target.value)}
                  />
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <Button
            variant="outline"
            onClick={() => setCurrentQuestionIndex(prev => Math.max(0, prev - 1))}
            disabled={currentQuestionIndex === 0}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Previous
          </Button>

          <div className="flex space-x-2">
            {questions.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentQuestionIndex(index)}
                className={`w-8 h-8 rounded-full text-sm font-medium transition-colors ${
                  index === currentQuestionIndex
                    ? 'bg-blue-600 text-white'
                    : answers[questions[index]?.id]
                    ? 'bg-green-100 text-green-700 border border-green-300'
                    : 'bg-gray-100 text-gray-600 border border-gray-300'
                }`}
              >
                {index + 1}
              </button>
            ))}
          </div>

          {isLastQuestion ? (
            <Button
              onClick={() => handleSubmitTest()}
              disabled={!canSubmit || submitTestMutation.isPending}
              className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
            >
              <Send className="h-4 w-4 mr-1" />
              {submitTestMutation.isPending ? 'Submitting...' : 'Submit Test'}
            </Button>
          ) : (
            <Button
              onClick={() => setCurrentQuestionIndex(prev => Math.min(questions.length - 1, prev + 1))}
              disabled={currentQuestionIndex === questions.length - 1}
              className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}
        </div>

        {/* Auto-save indicator */}
        {saveAnswerMutation.isPending && (
          <div className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg">
            Saving...
          </div>
        )}
      </div>
    </div>
    <Dialog open={timeUpOpen} onOpenChange={setTimeUpOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Time’s Up!</DialogTitle>
          <DialogDescription>
            Your time has expired. Submitting your test now...
          </DialogDescription>
        </DialogHeader>
        <div className="text-sm text-gray-600">Please wait while we finalize your submission.</div>
      </DialogContent>
    </Dialog>
    </>
  )
}
