'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useTests, useDeleteTest, useDashboardStats, useGenerateShareLink, useCurrentUser } from '@/hooks/useApi'
import { CreateTestForm } from '@/components/tests/create-test-form'
import { Plus, Eye, Trash2, Users, Clock, Target, BarChart3, Share2, Copy } from 'lucide-react'
import Link from 'next/link'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export default function TestsPage() {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [filter, setFilter] = useState('all')
  const [shareOpen, setShareOpen] = useState(false)
  const [shareUrl, setShareUrl] = useState('')
  const [sharingTestId, setSharingTestId] = useState<string | null>(null)
  const [shareError, setShareError] = useState<string>('')
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  
  const { data: tests, isLoading: testsLoading } = useTests({ 
    created_by_me: filter === 'mine',
    is_active: filter === 'active' ? true : undefined
  })
  const { data: dashboardStats } = useDashboardStats()
  const deleteTestMutation = useDeleteTest()
  const generateShareLink = useGenerateShareLink()
  const { data: me } = useCurrentUser()

  const handleCreateSuccess = (testId: string) => {
    setShowCreateForm(false)
    // Could navigate to test details or show success message
  }

  const handleShareTest = async (testId: string) => {
    try {
      setSharingTestId(testId)
      setShareOpen(true)
      setShareUrl('')
      setShareError('')
      const res = await generateShareLink.mutateAsync(testId)
      const origin = typeof window !== 'undefined' ? window.location.origin : ''
      const full = `${origin}${res.share_url}`
      setShareUrl(full)
    } catch (e: any) {
      const msg = e?.message || 'Failed to generate share link'
      setShareError(msg)
    }
  }

  const canCopy = useMemo(() => !!shareUrl, [shareUrl])

  const copyToClipboard = async () => {
    if (!shareUrl) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      alert('Link copied to clipboard')
    } catch (e) {
      alert('Failed to copy link')
    }
  }

  const handleDeleteTest = async (testId: string, testTitle: string) => {
    if (window.confirm(`Are you sure you want to delete "${testTitle}"? This will also delete all submissions.`)) {
      try {
        await deleteTestMutation.mutateAsync(testId)
      } catch (error) {
        alert('Failed to delete test')
      }
    }
  }

  if (showCreateForm) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <CreateTestForm
            onSuccess={handleCreateSuccess}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Test Management</h1>
              <p className="text-gray-600">Create and manage tests from your question banks</p>
            </div>
            <Button
              onClick={() => setShowCreateForm(true)}
              className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Test
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Tests</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboardStats?.total_tests || 0}</div>
              <p className="text-xs text-muted-foreground">Tests created</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Submissions</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboardStats?.total_submissions || 0}</div>
              <p className="text-xs text-muted-foreground">Test attempts</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Question Banks</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboardStats?.total_question_banks || 0}</div>
              <p className="text-xs text-muted-foreground">Available sources</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Questions</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboardStats?.total_questions || 0}</div>
              <p className="text-xs text-muted-foreground">Questions available</p>
            </CardContent>
          </Card>
        </div>

        {/* Filter Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              {[
                { key: 'all', label: 'All Tests' },
                { key: 'mine', label: 'My Tests' },
                { key: 'active', label: 'Active Tests' }
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

        {/* Tests List */}
        {!mounted || testsLoading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <div>Loading tests...</div>
          </div>
        ) : tests && tests.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {tests.map((test) => (
              <Card key={test.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{test.title}</CardTitle>
                  <CardDescription>
                    {test.description || 'No description provided'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Array.isArray((test as any).question_bank_names) && (test as any).question_bank_names.length > 0 && (
                      <div className="text-xs text-gray-600">
                        <span className="font-medium">Banks:</span>{' '}
                        {(test as any).question_bank_names.join(', ')}
                      </div>
                    )}
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Questions:</span>
                      <span className="font-medium">{test.num_questions}</span>
                    </div>
                    
                    {test.time_limit_minutes && (
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600">Time Limit:</span>
                        <span className="font-medium">{test.time_limit_minutes} min</span>
                      </div>
                    )}
                    
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Pass Threshold:</span>
                      <span className="font-medium">{test.pass_threshold}%</span>
                    </div>
                    
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Submissions:</span>
                      <span className="font-medium">{test.total_submissions || 0}</span>
                    </div>
                    
                    {test.average_score > 0 && (
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600">Avg Score:</span>
                        <span className="font-medium">{test.average_score.toFixed(1)}%</span>
                      </div>
                    )}
                    
                    <div className="flex justify-between items-center pt-2">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        test.is_active 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {test.is_active ? 'Active' : 'Inactive'}
                      </span>
                      
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        test.is_public 
                          ? 'bg-blue-100 text-blue-800' 
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {test.is_public ? 'Public' : 'Private'}
                      </span>
                    </div>
                    
                    <div className="flex space-x-2 pt-4">
                      <Link href={`/test/${test.id}`} className="flex-1">
                        <Button variant="outline" size="sm" className="w-full">
                          <Eye className="h-4 w-4 mr-1" />
                          View
                        </Button>
                      </Link>
                      {me?.id === test.created_by && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleShareTest(test.id)}
                          disabled={generateShareLink.isPending}
                        >
                          <Share2 className="h-4 w-4 mr-1" />
                          Share
                        </Button>
                      )}
                      
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDeleteTest(test.id, test.title)}
                        disabled={deleteTestMutation.isPending}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
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
              <h3 className="text-lg font-medium text-gray-900 mb-2">No tests found</h3>
              <p className="text-gray-600 mb-4">
                {filter === 'mine' 
                  ? "You haven't created any tests yet." 
                  : "No tests match your current filter."}
              </p>
              <Button
                onClick={() => setShowCreateForm(true)}
                className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Test
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Share Test</DialogTitle>
            <DialogDescription>
              Generate a secure share link to allow users to take this test.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {generateShareLink.isPending && (
              <div className="text-sm text-gray-600">Generating link...</div>
            )}
            {!!shareError && !generateShareLink.isPending && (
              <div className="text-sm text-red-600">{shareError}</div>
            )}
            {shareUrl && (
              <div className="flex items-center space-x-2">
                <input
                  className="flex-1 border rounded-md px-3 py-2 text-sm"
                  value={shareUrl}
                  readOnly
                />
                <Button onClick={copyToClipboard} disabled={!canCopy}>
                  <Copy className="h-4 w-4 mr-1" /> Copy
                </Button>
              </div>
            )}
            <div className="text-xs text-gray-500">
              Anyone with the link can take the test. They'll be asked for name and email if not logged in.
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShareOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
