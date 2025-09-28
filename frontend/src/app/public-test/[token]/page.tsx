'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { AlertCircle, Clock, Users, Target } from 'lucide-react'
import { motion } from 'framer-motion'
import { useToast } from '@/components/ui/toast'

export default function PublicTestPage() {
  const params = useParams()
  const router = useRouter()
  const token = params.token as string
  const { addToast } = useToast()
  
  const [loading, setLoading] = useState(true)
  const [testData, setTestData] = useState<any>(null)
  const [participantName, setParticipantName] = useState('')
  const [participantEmail, setParticipantEmail] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchTestData = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/test-sharing/public/${token}`)
        if (!response.ok) {
          throw new Error('Test not found or expired')
        }
        const data = await response.json()
        setTestData(data)
      } catch (err: any) {
        setError(err.message || 'Failed to load test')
      } finally {
        setLoading(false)
      }
    }

    if (token) {
      fetchTestData()
    }
  }, [token])

  const handleStartTest = () => {
    if (!participantName.trim()) {
      addToast('Please enter your name', 'error')
      return
    }

    if (participantEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(participantEmail)) {
      addToast('Please enter a valid email address', 'error')
      return
    }

    // Navigate to the test taking page with participant info
    const searchParams = new URLSearchParams({
      name: participantName,
      email: participantEmail || '',
      token: token
    })
    
    router.push(`/test/${testData.test_id}?${searchParams.toString()}`)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-cyan-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <div>Loading test...</div>
        </div>
      </div>
    )
  }

  if (error || !testData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-cyan-50">
        <Card className="w-full max-w-md text-center shadow-xl">
          <CardContent className="py-8">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2 text-gray-900">Test Not Available</h2>
            <p className="text-gray-600 mb-4">{error}</p>
            <Button onClick={() => window.history.back()}>Go Back</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-cyan-50">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Card className="shadow-xl">
            <CardHeader className="text-center bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-t-lg">
              <CardTitle className="text-2xl font-bold">
                {testData.title}
              </CardTitle>
              <CardDescription className="text-blue-100">
                {testData.description || 'Welcome to this test'}
              </CardDescription>
            </CardHeader>
            
            <CardContent className="p-8">
              {/* Test Information */}
              <div className="bg-blue-50 p-6 rounded-lg mb-6">
                <h3 className="font-semibold text-gray-900 mb-4 flex items-center">
                  <Target className="h-5 w-5 mr-2" />
                  Test Information
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div className="flex items-center">
                    <Users className="h-4 w-4 mr-2 text-blue-600" />
                    <span className="text-gray-600">Questions:</span>
                    <span className="ml-2 font-medium">{testData.num_questions}</span>
                  </div>
                  {testData.time_limit_minutes && (
                    <div className="flex items-center">
                      <Clock className="h-4 w-4 mr-2 text-blue-600" />
                      <span className="text-gray-600">Time Limit:</span>
                      <span className="ml-2 font-medium">{testData.time_limit_minutes} minutes</span>
                    </div>
                  )}
                  <div className="flex items-center">
                    <Target className="h-4 w-4 mr-2 text-blue-600" />
                    <span className="text-gray-600">Pass Threshold:</span>
                    <span className="ml-2 font-medium">{testData.pass_threshold}%</span>
                  </div>
                </div>
              </div>

              {/* Participant Information Form */}
              <div className="space-y-6">
                <h3 className="font-semibold text-gray-900">Enter Your Information</h3>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Full Name *</Label>
                    <Input
                      id="name"
                      type="text"
                      value={participantName}
                      onChange={(e) => setParticipantName(e.target.value)}
                      placeholder="Enter your full name"
                      className="w-full"
                      required
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address</Label>
                    <Input
                      id="email"
                      type="email"
                      value={participantEmail}
                      onChange={(e) => setParticipantEmail(e.target.value)}
                      placeholder="Enter your email (optional)"
                      className="w-full"
                    />
                    <p className="text-xs text-gray-600">
                      Your email will be used to retrieve your results later
                    </p>
                  </div>
                </div>

                <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
                  <div className="flex items-start">
                    <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5 mr-3 flex-shrink-0" />
                    <div className="text-sm">
                      <p className="font-medium text-yellow-800 mb-1">Before you start:</p>
                      <ul className="text-yellow-700 space-y-1">
                        <li>• Make sure you have a stable internet connection</li>
                        <li>• Complete the test in one session</li>
                        <li>• Your progress will be saved automatically</li>
                        {testData.time_limit_minutes && (
                          <li>• You have {testData.time_limit_minutes} minutes to complete the test</li>
                        )}
                      </ul>
                    </div>
                  </div>
                </div>

                <Button
                  onClick={handleStartTest}
                  className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 py-3 text-lg font-medium"
                  disabled={!participantName.trim()}
                >
                  Start Test
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
