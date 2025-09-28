'use client'

import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { CheckCircle, XCircle, Clock, Target, Home, RotateCcw, Mail } from 'lucide-react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { useToast } from '@/components/ui/toast'

export default function TestResultsPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()
  const testId = params.testId as string
  const emailParam = searchParams?.get('email') || ''
  const { addToast } = useToast()
  
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [email, setEmail] = useState(emailParam)
  const [error, setError] = useState('')

  const fetchResultByEmail = async (testId: string, email: string) => {
    try {
      setLoading(true)
      setError('')
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/test-taking/results/${testId}/${encodeURIComponent(email)}`
      )
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('No results found for this email address')
        }
        throw new Error('Failed to fetch results')
      }
      
      const data = await response.json()
      setResult(data)
    } catch (err: any) {
      setError(err.message)
      addToast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (emailParam && testId) {
      fetchResultByEmail(testId, emailParam)
    }
  }, [emailParam, testId])

  const handleSearchResults = () => {
    if (!email.trim()) {
      addToast('Please enter your email address', 'error')
      return
    }
    
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      addToast('Please enter a valid email address', 'error')
      return
    }
    
    fetchResultByEmail(testId, email)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <div>Loading your results...</div>
        </div>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="shadow-xl">
              <CardHeader className="text-center">
                <CardTitle className="text-2xl font-bold text-gray-900 flex items-center justify-center">
                  <Mail className="h-6 w-6 mr-2" />
                  Find Your Test Results
                </CardTitle>
                <CardDescription>
                  Enter your email address to retrieve your test results
                </CardDescription>
              </CardHeader>
              
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address</Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter the email you used for the test"
                      className="w-full"
                      onKeyDown={(e) => e.key === 'Enter' && handleSearchResults()}
                    />
                  </div>
                  
                  {error && (
                    <div className="text-sm text-red-600 bg-red-50 border border-red-200 p-3 rounded-lg">
                      {error}
                    </div>
                  )}
                  
                  <Button
                    onClick={handleSearchResults}
                    disabled={loading || !email.trim()}
                    className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
                  >
                    {loading ? 'Searching...' : 'Get My Results'}
                  </Button>
                </div>
                
                <div className="text-center">
                  <Link href="/dashboard">
                    <Button variant="outline">Back to Dashboard</Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    )
  }

  const percentage = result.score
  const isPassed = result.is_passed

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
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
              
              <div className="text-sm text-gray-600 mt-2">
                Results for: {result.participant_email}
              </div>
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
                    Required: 70%
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Detailed Results */}
          {result.question_results && (
            <Card className="mb-8 shadow-lg">
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
                    <motion.div 
                      key={questionResult.question_id} 
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.1 }}
                      className={`p-4 rounded-lg border-l-4 ${
                        questionResult.is_correct 
                          ? 'bg-green-50 border-green-400' 
                          : 'bg-red-50 border-red-400'
                      }`}
                    >
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
                    </motion.div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Actions */}
          <div className="flex justify-center space-x-4">
            <Link href={`/public-test/${searchParams?.get('token') || 'direct'}`}>
              <Button variant="outline" className="flex items-center space-x-2">
                <Home className="h-4 w-4" />
                <span>Back to Test</span>
              </Button>
            </Link>
            
            <Link href={`/test/${result.test_id}?email=${result.participant_email}`}>
              <Button 
                className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 flex items-center space-x-2"
              >
                <RotateCcw className="h-4 w-4" />
                <span>Take Again</span>
              </Button>
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
