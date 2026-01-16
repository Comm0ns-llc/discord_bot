'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar
} from 'recharts'
import { Users, MessageSquare, Flame, TrendingUp } from 'lucide-react'

// Types
interface DailyPulse {
  day: string
  total_messages: number
  active_users: number
  total_score: number
  avg_quality: number
}

interface LeaderboardEntry {
  user_id: number
  username: string
  current_score: number
  weekly_score: number
  total_messages: number
}

// Stat Card Component
function StatCard({
  title,
  value,
  description,
  icon: Icon,
  trend
}: {
  title: string
  value: string | number
  description?: string
  icon: React.ElementType
  trend?: { value: number; positive: boolean }
}) {
  return (
    <Card className="bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/30 transition-colors">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
        {trend && (
          <div className={`text-xs mt-1 ${trend.positive ? 'text-green-500' : 'text-red-500'}`}>
            {trend.positive ? '↑' : '↓'} {Math.abs(trend.value).toFixed(1)}% from last week
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function HomePage() {
  const [dailyPulse, setDailyPulse] = useState<DailyPulse[]>([])
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      const supabase = createClient()
      setIsLoading(true)
      setError(null)

      try {
        // Fetch Daily Pulse (last 14 days)
        const { data: pulseData, error: pulseError } = await supabase
          .from('analytics_daily_pulse')
          .select('*')
          .order('day', { ascending: true })
          .limit(365) // Last year

        if (pulseError) throw pulseError
        setDailyPulse(pulseData || [])

        // Fetch Leaderboard (Top 5)
        const { data: leaderData, error: leaderError } = await supabase
          .from('analytics_leaderboard')
          .select('*')
          .order('current_score', { ascending: false })
          .limit(5)

        if (leaderError) throw leaderError
        setLeaderboard(leaderData || [])

      } catch (err) {
        console.error('Failed to fetch data:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch data')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  // Calculate summary stats
  const totalMessages = dailyPulse.reduce((sum, d) => sum + Number(d.total_messages), 0)
  const totalScore = dailyPulse.reduce((sum, d) => sum + Number(d.total_score), 0)
  const avgQuality = dailyPulse.length > 0
    ? dailyPulse.reduce((sum, d) => sum + Number(d.avg_quality), 0) / dailyPulse.length
    : 0
  const peakActiveUsers = dailyPulse.length > 0
    ? Math.max(...dailyPulse.map(d => Number(d.active_users)))
    : 0

  // Format chart data
  const chartData = dailyPulse.map(d => ({
    ...d,
    day: new Date(d.day).toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' }),
    total_score: Number(d.total_score),
    total_messages: Number(d.total_messages),
    active_users: Number(d.active_users),
  }))

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-pulse text-muted-foreground">Loading analytics...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-destructive">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Community health at a glance</p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Messages (365d)"
          value={totalMessages.toLocaleString()}
          icon={MessageSquare}
        />
        <StatCard
          title="Total Score"
          value={totalScore.toFixed(0)}
          icon={Flame}
        />
        <StatCard
          title="Avg. Quality"
          value={avgQuality.toFixed(2)}
          description="NLP quality multiplier"
          icon={TrendingUp}
        />
        <StatCard
          title="Peak Active Users"
          value={peakActiveUsers}
          icon={Users}
        />
      </div>

      {/* Charts Section */}
      <div className="grid gap-6 lg:grid-cols-7">
        {/* Activity Chart */}
        <Card className="lg:col-span-4 bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Activity Pulse (Messages)</CardTitle>
            <CardDescription>Daily message volume over the last year</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="day"
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={30}
                />
                <YAxis
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '12px'
                  }}
                  cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
                />
                <Bar
                  dataKey="total_messages"
                  fill="hsl(var(--primary))"
                  radius={[2, 2, 0, 0]}
                  name="Messages"
                  maxBarSize={50}
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Leaderboard Preview */}
        <Card className="lg:col-span-3 bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Top Contributors</CardTitle>
            <CardDescription>Leading members by cumulative score</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {leaderboard.map((user, index) => (
                <div key={user.user_id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={index < 3 ? "default" : "secondary"}
                      className={
                        index === 0 ? "bg-yellow-500/80" :
                          index === 1 ? "bg-gray-400/80" :
                            index === 2 ? "bg-orange-600/80" : ""
                      }
                    >
                      #{index + 1}
                    </Badge>
                    <div>
                      <p className="font-medium text-sm">{user.username}</p>
                      <p className="text-xs text-muted-foreground">{user.total_messages} messages</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{Number(user.current_score).toFixed(0)}</p>
                    <p className="text-xs text-muted-foreground">pts</p>
                  </div>
                </div>
              ))}
              {leaderboard.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">No data yet</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Users Chart */}
      <Card className="bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Daily Active Users</CardTitle>
          <CardDescription>Unique participants per day</CardDescription>
        </CardHeader>
        <CardContent className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px'
                }}
              />
              <Bar dataKey="active_users" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} name="Active Users" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}
