'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useRouter } from 'next/navigation'
import { Upload, FileText, BarChart3, Users, Activity } from 'lucide-react'
import { useHealthCheck, useCurrentUser, useLogout, useQuestionBanks, useUploadQuestionBank, useDashboardStats, useDeleteQuestionBank, useUpdateQuestionBank } from '@/hooks/useApi'
import Link from 'next/link'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { motion, AnimatePresence } from 'framer-motion'

export default function DashboardPage() {
  const [editOpen, setEditOpen] = useState(false)
  const [editingBank, setEditingBank] = useState<any | null>(null)
  const [editedName, setEditedName] = useState('')
  const [editedDesc, setEditedDesc] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const router = useRouter()
  
  // API hooks
  const { data: healthData, isLoading: healthLoading, error: healthError } = useHealthCheck()
  const { data: user, isLoading: userLoading, error: userError } = useCurrentUser()
  const { data: questionBanks, isLoading: questionBanksLoading } = useQuestionBanks()
  const { data: dashboardStats, isLoading: statsLoading } = useDashboardStats()
  const logoutMutation = useLogout()
  const uploadMutation = useUploadQuestionBank()
  const deleteBankMutation = useDeleteQuestionBank()
  const updateBankMutation = useUpdateQuestionBank()
  const { addToast } = useToast()


  const openEditBank = (bank: any) => {
    setEditingBank(bank)
    setEditedName(bank.name || '')
    setEditedDesc(bank.description || '')
    setEditOpen(true)
  }

  const saveEditBank = async () => {
    if (!editingBank) return
    try {
      await updateBankMutation.mutateAsync({ id: editingBank.id, update: { name: editedName || undefined, description: editedDesc || undefined } })
      setEditOpen(false)
      setEditingBank(null)
      addToast('Question bank updated successfully! ✅', 'success')
    } catch (e: any) {
      addToast(e?.message || 'Failed to update question bank', 'error')
    }
  }

  const deleteBank = async (bank: any) => {
    if (!window.confirm(`Delete question bank "${bank.name}"? This will delete all its questions.`)) return
    try {
      await deleteBankMutation.mutateAsync(bank.id)
      addToast('Question bank deleted successfully! 🗑️', 'success')
    } catch (e: any) {
      addToast(e?.message || 'Failed to delete question bank', 'error')
    }
  }

  const handleLogout = async () => {
    try {
      await logoutMutation.mutateAsync()
      router.push('/login')
    } catch (error) {
      // Even if logout API fails, clear local storage and redirect
      router.push('/login')
    }
  }

  const handleUploadQuestionBank = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const fileName = file.name.replace(/\.[^/.]+$/, "")
    uploadMutation.mutate(
      {
        file,
        metadata: {
          name: fileName,
          description: `Uploaded via dashboard on ${new Date().toLocaleDateString()}`
        }
      },
      {
        onSuccess: (data) => {
          addToast(`Question Bank Uploaded ✅ - ${data.questions_imported} questions imported!`, 'success')
          // Reset file input
          event.target.value = ''
        },
        onError: (error: any) => {
          addToast(`Upload failed: ${error.message || 'Unknown error'}`, 'error')
        }
      }
    )
  }

  // Calculate stats - use enhanced dashboard stats when available
  const totalQuestionBanks = dashboardStats?.total_question_banks || questionBanks?.length || 0
  const totalQuestions = dashboardStats?.total_questions || questionBanks?.reduce((sum, qb) => sum + (qb.question_count || 0), 0) || 0
  const totalTests = dashboardStats?.total_tests || 0
  const totalSubmissions = dashboardStats?.total_submissions || 0

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <h1 className="text-xl font-semibold text-gray-900">
              Question Bank Management System
            </h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">
                Welcome, {user?.name || user?.email}
              </span>
              <Button 
                variant="outline" 
                onClick={handleLogout}
                disabled={logoutMutation.isPending}
              >
                {logoutMutation.isPending ? 'Logging out...' : 'Logout'}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Admin Dashboard</h2>
          <p className="text-gray-600">Manage your question banks and upload new content</p>
        </div>

        {/* Backend Status Card */}
        <div className="mb-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Backend Status</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2">
                {healthLoading ? (
                  <div className="text-sm text-yellow-600">Checking...</div>
                ) : healthError ? (
                  <div className="text-sm text-red-600">❌ Backend Offline</div>
                ) : healthData?.status === 'ok' ? (
                  <div className="text-sm text-green-600">✅ Backend Online</div>
                ) : (
                  <div className="text-sm text-gray-600">Unknown Status</div>
                )}

        {/* Manage Question Banks */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <FileText className="h-5 w-5" />
              <span>Manage Question Banks</span>
            </CardTitle>
            <CardDescription>View, rename, or delete your uploaded banks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-4">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search banks by name..."
                className="w-full md:w-96 border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {searchTerm && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSearchTerm('')}
                  className="ml-2"
                >
                  Clear
                </Button>
              )}
            </div>
            {!questionBanks || questionBanks.length === 0 ? (
              <div className="text-sm text-gray-600">No question banks uploaded yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600 border-b">
                      <th className="py-2 pr-4 font-semibold">Name</th>
                      <th className="py-2 pr-4 font-semibold">Questions</th>
                      <th className="py-2 pr-4 font-semibold">Created</th>
                      <th className="py-2 pr-4 font-semibold">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(questionBanks as any[]).filter((qb) => 
                      !searchTerm || qb.name?.toLowerCase().includes(searchTerm.toLowerCase())
                    ).map((qb: any, index: number) => (
                      <motion.tr 
                        key={qb.id} 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="border-b hover:bg-gray-50"
                        whileHover={{ backgroundColor: "rgb(249 250 251)" }}
                      >
                        <td className="py-2 pr-4">
                          <div className="font-medium text-gray-900">{qb.name}</div>
                          <div className="text-xs text-gray-600">{qb.description || '—'}</div>
                        </td>
                        <td className="py-2 pr-4">{qb.question_count || 0}</td>
                        <td className="py-2 pr-4">{new Date(qb.created_at).toLocaleDateString()}</td>
                        <td className="py-2 pr-4 space-x-2">
                          <motion.div
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            style={{ display: 'inline-block' }}
                          >
                            <Button variant="outline" size="sm" onClick={() => openEditBank(qb)}>Edit</Button>
                          </motion.div>
                          <motion.div
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            style={{ display: 'inline-block' }}
                          >
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => deleteBank(qb)}
                              disabled={deleteBankMutation.isPending}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            >
                              Delete
                            </Button>
                          </motion.div>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {healthData?.message || 'FastAPI backend connectivity'}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Navigation */}
        <div className="mb-8">
          <div className="flex flex-wrap gap-2">
            <Link href="/dashboard">
              <Button variant="default" className="bg-gradient-to-r from-blue-600 to-cyan-600">
                Dashboard
              </Button>
            </Link>
            <Link href="/dashboard/tests">
              <Button variant="outline">
                Test Management
              </Button>
            </Link>
            <Link href="/dashboard/attempts">
              <Button variant="outline">
                My Attempts
              </Button>
            </Link>
            <Link href="/dashboard/analytics">
              <Button variant="outline">
                Analytics
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="hover:shadow-lg transition-shadow duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Question Banks</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalQuestionBanks}</div>
              <p className="text-xs text-muted-foreground">
                {statsLoading ? 'Loading...' : totalQuestionBanks === 0 ? 'No question banks yet' : 'Banks uploaded'}
              </p>
            </CardContent>
          </Card>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="hover:shadow-lg transition-shadow duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Questions</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalQuestions}</div>
              <p className="text-xs text-muted-foreground">
                {statsLoading ? 'Loading...' : totalQuestions === 0 ? 'No questions uploaded' : 'Questions available'}
              </p>
            </CardContent>
          </Card>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="hover:shadow-lg transition-shadow duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Tests</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalTests}</div>
              <p className="text-xs text-muted-foreground">
                {statsLoading ? 'Loading...' : totalTests === 0 ? 'No tests created' : 'Tests available'}
              </p>
            </CardContent>
          </Card>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card className="hover:shadow-lg transition-shadow duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Submissions</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{totalSubmissions}</div>
              <p className="text-xs text-muted-foreground">
                {statsLoading ? 'Loading...' : totalSubmissions === 0 ? 'No submissions yet' : 'Test attempts'}
              </p>
            </CardContent>
          </Card>
          </motion.div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href="/dashboard/tests">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2 text-blue-600">
                  <Activity className="h-5 w-5" />
                  <span>Manage Tests</span>
                </CardTitle>
                <CardDescription>
                  Create, edit, and monitor your tests
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-600">
                  {totalTests > 0 ? `${totalTests} tests created` : 'Create your first test'}
                </div>
              </CardContent>
            </Link>
          </Card>
          
          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href="/dashboard/analytics">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2 text-green-600">
                  <BarChart3 className="h-5 w-5" />
                  <span>View Analytics</span>
                </CardTitle>
                <CardDescription>
                  Monitor performance and results
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-600">
                  {totalSubmissions > 0 ? `${totalSubmissions} submissions to analyze` : 'No submissions yet'}
                </div>
              </CardContent>
            </Link>
          </Card>
        </div>

        {/* Recent Tests Section */}
        {dashboardStats?.recent_tests && dashboardStats.recent_tests.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Activity className="h-5 w-5" />
                <span>Available Tests</span>
              </CardTitle>
              <CardDescription>
                Tests you can take or manage
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {dashboardStats.recent_tests.map((test: any) => (
                  <div key={test.id} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h4 className="font-medium text-gray-900">{test.title}</h4>
                        <p className="text-sm text-gray-600">{test.description || 'No description'}</p>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        test.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {test.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    
                    <div className="text-xs text-gray-500 space-y-1 mb-3">
                      <div>Questions: {test.num_questions}</div>
                      {test.time_limit_minutes && <div>Time: {test.time_limit_minutes} min</div>}
                      <div>Pass: {test.pass_threshold}%</div>
                      {test.total_submissions > 0 && (
                        <div>Submissions: {test.total_submissions} (Avg: {test.average_score.toFixed(1)}%)</div>
                      )}
                    </div>
                    
                    <div className="flex space-x-2">
                      <Link href={`/test/${test.id}`} className="flex-1">
                        <Button 
                          size="sm" 
                          className="w-full bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                          disabled={!test.is_active}
                        >
                          Take Test
                        </Button>
                      </Link>
                      <Link href={`/dashboard/tests`}>
                        <Button variant="outline" size="sm">
                          Manage
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Upload className="h-5 w-5" />
              <span>Upload Question Bank</span>
            </CardTitle>
            <CardDescription>
              Upload Excel or CSV files containing your questions and answers
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col space-y-4">
              <div className="border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg p-8 text-center transition-colors">
                <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <p className="text-sm text-gray-600 mb-4">
                  Select your Excel/CSV files to upload question banks
                </p>
                <div className="relative">
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={handleUploadQuestionBank}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={uploadMutation.isPending}
                  />
                  <Button 
                    className="mx-auto bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700"
                    disabled={uploadMutation.isPending}
                  >
                    {uploadMutation.isPending ? 'Uploading...' : 'Choose Files'}
                  </Button>
                </div>
              </div>
              <div className="text-xs text-gray-500">
                <p>Supported formats: .xlsx, .xls, .csv</p>
                <p>Maximum file size: 10MB</p>
                <p>Required columns: question, correct_answer</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Question Bank</DialogTitle>
            <DialogDescription>Rename or update the description.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-gray-700">Name</label>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={editedName}
                onChange={(e) => setEditedName(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm text-gray-700">Description</label>
              <textarea
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={editedDesc}
                onChange={(e) => setEditedDesc(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button onClick={saveEditBank} disabled={updateBankMutation.isPending} className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700">
              {updateBankMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
