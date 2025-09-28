'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useUserAttempts, useUserPerformance } from '@/hooks/useApi'
import { CheckCircle, XCircle, Clock, Target, Eye, BarChart3 } from 'lucide-react'
import Link from 'next/link'

export default function AttemptsPage() {
  const [filter, setFilter] = useState('all')
  
  const { data: attempts, isLoading: attemptsLoading } = useUserAttempts()
  const { data: performance, isLoading: performanceLoading } = useUserPerformance()

  const filteredAttempts = attempts?.filter(attempt => {
    if (filter === 'passed') return attempt.is_passed
    if (filter === 'failed') return !attempt.is_passed
    return true
  }) || []

  const stats = {
    totalAttempts: attempts?.length || 0,
    passedTests: attempts?.filter(a => a.is_passed).length || 0,
    averageScore: attempts && attempts.length > 0 
      ? attempts.reduce((sum, a) => sum + a.score, 0) / attempts.length 
      : 0,
    totalTime: attempts?.reduce((sum, a) => sum + (a.time_taken_minutes || 0), 0) || 0
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">My Test Attempts</h1>
              <p className="text-gray-600">Track your progress and review past results</p>
            </div>
            <Link href="/dashboard">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Performance Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Attempts</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalAttempts}</div>
              <p className="text-xs text-muted-foreground">Tests taken</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Tests Passed</CardTitle>
              <CheckCircle className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.passedTests}</div>
              <p className="text-xs text-muted-foreground">
                {stats.totalAttempts > 0 ? `${((stats.passedTests / stats.totalAttempts) * 100).toFixed(1)}% pass rate` : 'No attempts yet'}
              </p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Average Score</CardTitle>
              <BarChart3 className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {stats.averageScore.toFixed(1)}%
              </div>
              <p className="text-xs text-muted-foreground">Across all attempts</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Time</CardTitle>
              <Clock className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-600">{stats.totalTime}</div>
              <p className="text-xs text-muted-foreground">Minutes spent</p>
            </CardContent>
          </Card>
        </div>

        {/* Filter Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              {[
                { key: 'all', label: 'All Attempts' },
                { key: 'passed', label: 'Passed' },
                { key: 'failed', label: 'Failed' }
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    filter === tab.key
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Attempts List */}
        {attemptsLoading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <div>Loading attempts...</div>
          </div>
        ) : filteredAttempts.length > 0 ? (
          <div className="space-y-4">
            {filteredAttempts.map((attempt) => (
              <Card key={attempt.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                        attempt.is_passed ? 'bg-green-100' : 'bg-red-100'
                      }`}>
                        {attempt.is_passed ? (
                          <CheckCircle className="h-6 w-6 text-green-600" />
                        ) : (
                          <XCircle className="h-6 w-6 text-red-600" />
                        )}
                      </div>
                      
                      <div>
                        <h3 className="font-semibold text-gray-900">{attempt.test_title}</h3>
                        <p className="text-sm text-gray-600">
                          Submitted on {new Date(attempt.submitted_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-6">
                      <div className="text-center">
                        <div className={`text-2xl font-bold ${
                          attempt.is_passed ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {attempt.score.toFixed(1)}%
                        </div>
                        <div className="text-xs text-gray-500">Score</div>
                      </div>
                      
                      <div className="text-center">
                        <div className="text-lg font-medium text-gray-900">
                          {attempt.correct_answers}/{attempt.total_questions}
                        </div>
                        <div className="text-xs text-gray-500">Correct</div>
                      </div>
                      
                      <div className="text-center">
                        <div className="text-lg font-medium text-gray-900">
                          {attempt.time_taken_minutes || 0}m
                        </div>
                        <div className="text-xs text-gray-500">Time</div>
                      </div>
                      
                      <Link href={`/results/${attempt.id}`}>
                        <Button variant="outline" size="sm">
                          <Eye className="h-4 w-4 mr-1" />
                          View Details
                        </Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="text-center py-12">
            <CardContent>
              <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No attempts found</h3>
              <p className="text-gray-600 mb-4">
                {filter === 'all' 
                  ? "You haven't taken any tests yet." 
                  : `No ${filter} attempts found.`}
              </p>
              <Link href="/dashboard">
                <Button className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700">
                  Browse Available Tests
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

