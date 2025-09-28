'use client'

import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useTests, useTestSubmissions, useTestLeaderboardForTest } from '@/hooks/useApi'
import { Download, Filter, Trophy, User, Calendar, BarChart3 } from 'lucide-react'

export default function AnalyticsPage() {
  const [selectedTestId, setSelectedTestId] = useState<string>('')
  const [filters, setFilters] = useState<{ start_date?: string; end_date?: string; user?: string }>({})

  const { data: tests } = useTests({ created_by_me: true })
  useEffect(() => {
    if (!selectedTestId && tests && tests.length > 0) {
      setSelectedTestId(tests[0].id)
    }
  }, [tests, selectedTestId])
  const selectedTest = useMemo(() => tests?.find((t: any) => t.id === selectedTestId), [tests, selectedTestId])
  const { data: submissions } = useTestSubmissions(selectedTestId || '', {
    start_date: filters.start_date,
    end_date: filters.end_date,
    user: filters.user,
    limit: 100,
  })
  const { data: leaderboard } = useTestLeaderboardForTest(selectedTestId || '', 20)

  const handleExport = async () => {
    if (!selectedTestId) {
      alert('Please select a test to export')
      return
    }
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/tests/${selectedTestId}/export`, {
        headers: typeof window !== 'undefined' && localStorage.getItem('auth_token')
          ? { Authorization: `Bearer ${localStorage.getItem('auth_token')}` }
          : {},
      })
      if (!res.ok) {
        alert('Failed to export CSV')
        return
      }
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `test_${selectedTestId}_results.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      alert('Export failed')
    }
  }

  const summary = useMemo(() => {
    const data = submissions || []
    const total = data.length
    const avgScore = total > 0 ? data.reduce((s: number, r: any) => s + (r.score || 0), 0) / total : 0
    const avgTime = total > 0 ? data.reduce((s: number, r: any) => s + (r.time_taken_minutes || 0), 0) / total : 0
    const passRate = total > 0 ? (data.filter((r: any) => r.is_passed).length / total) * 100 : 0
    return { total, avgScore, avgTime, passRate }
  }, [submissions])

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
              <p className="text-gray-600">View test performance and export results</p>
            </div>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2"><Filter className="h-5 w-5" /><span>Filters</span></CardTitle>
            <CardDescription>Choose a test and narrow down by dates or user</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="md:col-span-2">
                <label className="text-sm text-gray-700">Test</label>
                <select
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={selectedTestId}
                  onChange={(e) => setSelectedTestId(e.target.value)}
                >
                  <option value="">Select a test</option>
                  {tests?.map((t: any) => (
                    <option key={t.id} value={t.id}>{t.title}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm text-gray-700 flex items-center space-x-1"><Calendar className="h-4 w-4" /><span>Start date</span></label>
                <Input type="date" value={filters.start_date || ''} onChange={(e) => setFilters(f => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm text-gray-700 flex items-center space-x-1"><Calendar className="h-4 w-4" /><span>End date</span></label>
                <Input type="date" value={filters.end_date || ''} onChange={(e) => setFilters(f => ({ ...f, end_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm text-gray-700 flex items-center space-x-1"><User className="h-4 w-4" /><span>User</span></label>
                <Input placeholder="Search name or email" value={filters.user || ''} onChange={(e) => setFilters(f => ({ ...f, user: e.target.value }))} />
              </div>
            </div>
            {Array.isArray((selectedTest as any)?.question_bank_names) && (selectedTest as any).question_bank_names.length > 0 && (
              <div className="text-xs text-gray-600 mt-2">
                <span className="font-medium">Included Banks:</span> {(selectedTest as any).question_bank_names.join(', ')}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Total Attempts</CardTitle>
              <CardDescription>Submissions counted</CardDescription>
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{summary.total}</div></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Average Score</CardTitle>
              <CardDescription>Across filtered submissions</CardDescription>
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{summary.avgScore.toFixed(1)}%</div></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Average Time</CardTitle>
              <CardDescription>Minutes</CardDescription>
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{summary.avgTime.toFixed(0)}m</div></CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Pass Rate</CardTitle>
              <CardDescription>Across filtered submissions</CardDescription>
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{summary.passRate.toFixed(1)}%</div></CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2"><BarChart3 className="h-5 w-5" /><span>Submissions</span></CardTitle>
            <CardDescription>Attempts with name, email, score, time</CardDescription>
          </CardHeader>
          <CardContent>
            {(!submissions || submissions.length === 0) ? (
              <div className="text-sm text-gray-600">No submissions found for the selected filters.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600">
                      <th className="py-2 pr-4">Attempt Date</th>
                      <th className="py-2 pr-4">User Name</th>
                      <th className="py-2 pr-4">User Email</th>
                      <th className="py-2 pr-4">Score</th>
                      <th className="py-2 pr-4">Time Taken</th>
                      <th className="py-2 pr-4">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {submissions.map((s: any) => (
                      <tr key={s.id} className="border-t">
                        <td className="py-2 pr-4">{new Date(s.submitted_at).toLocaleString()}</td>
                        <td className="py-2 pr-4">{s.participant_name}</td>
                        <td className="py-2 pr-4">{s.participant_email || '-'}</td>
                        <td className="py-2 pr-4">{(s.score ?? 0).toFixed(1)}%</td>
                        <td className="py-2 pr-4">{s.time_taken_minutes || 0}m</td>
                        <td className="py-2 pr-4">{s.is_passed ? 'Passed' : 'Failed'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-4">
              <Button onClick={handleExport} disabled={!selectedTestId}>
                <Download className="h-4 w-4 mr-1" /> Download CSV
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2"><Trophy className="h-5 w-5" /><span>Leaderboard</span></CardTitle>
            <CardDescription>Best scores per user</CardDescription>
          </CardHeader>
          <CardContent>
            {(!leaderboard || leaderboard.length === 0) ? (
              <div className="text-sm text-gray-600">No leaderboard data yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600">
                      <th className="py-2 pr-4">Name</th>
                      <th className="py-2 pr-4">Email</th>
                      <th className="py-2 pr-4">Best Score</th>
                      <th className="py-2 pr-4">Attempts</th>
                      <th className="py-2 pr-4">Last Attempt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.map((r: any, idx: number) => (
                      <tr key={`${r.email}-${idx}`} className="border-t">
                        <td className="py-2 pr-4">{r.name}</td>
                        <td className="py-2 pr-4">{r.email}</td>
                        <td className="py-2 pr-4">{(r.best_score ?? 0).toFixed(1)}%</td>
                        <td className="py-2 pr-4">{r.attempts}</td>
                        <td className="py-2 pr-4">{r.last_attempt ? new Date(r.last_attempt).toLocaleString() : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
