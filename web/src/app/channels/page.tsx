'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
	BarChart,
	Bar,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	Cell
} from 'recharts'
import { MessageSquare, Users, Crown } from 'lucide-react'

// Types based on SQL Views
interface ChannelRanking {
	channel_id: number // Note: The view returns channel_id as number/bigint
	channel_name: string
	total_messages: number
	active_users: number
	total_score: number
	avg_quality: number
	last_active: string
}

interface ChannelTopUser {
	channel_id: number
	channel_name: string
	user_id: number
	username: string
	message_count: number
}

interface ChannelData extends ChannelRanking {
	top_user?: ChannelTopUser
}

export default function ChannelsPage() {
	const [channels, setChannels] = useState<ChannelData[]>([])
	const [isLoading, setIsLoading] = useState(true)
	const [error, setError] = useState<string | null>(null)

	useEffect(() => {
		async function fetchData() {
			const supabase = createClient()
			setIsLoading(true)
			setError(null)

			try {
				// Fetch Channel Rankings
				const { data: rankingData, error: rankingError } = await supabase
					.from('analytics_channel_ranking')
					.select('*')
					.order('total_messages', { ascending: false })
					.limit(20)

				if (rankingError) throw rankingError

				// Fetch Top Users
				// Ideally we would fetch per channel, but for now we can fetch all and map
				// Or if the dataset is large, we should filter. 
				// Let's fetch the top users for the channels we just got.
				// Actually, the view `analytics_channel_leader_user` has one row per channel.
				// We can fetch all and match them in JS.
				const { data: topUserData, error: topUserError } = await supabase
					.from('analytics_channel_leader_user')
					.select('*')

				if (topUserError) throw topUserError

				// Merge Data
				const mergedData = (rankingData || []).map(channel => {
					const topUser = (topUserData || []).find(u => u.channel_id === channel.channel_id)
					return { ...channel, top_user: topUser }
				})

				setChannels(mergedData)

			} catch (err) {
				console.error('Failed to fetch channel data:', err)
				setError(err instanceof Error ? err.message : 'Failed to fetch data')
			} finally {
				setIsLoading(false)
			}
		}

		fetchData()
	}, [])

	if (isLoading) {
		return (
			<div className="flex items-center justify-center h-96">
				<div className="animate-pulse text-muted-foreground">Loading channel analytics...</div>
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
			<div>
				<h1 className="text-3xl font-bold tracking-tight">Channels</h1>
				<p className="text-muted-foreground">Activity rankings and top contributors by channel</p>
			</div>

			<div className="grid gap-6">
				{/* Chart Section */}
				<Card className="bg-card/50 backdrop-blur-sm">
					<CardHeader>
						<CardTitle>Top Active Channels</CardTitle>
						<CardDescription>By message volume</CardDescription>
					</CardHeader>
					<CardContent className="h-[300px]">
						<ResponsiveContainer width="100%" height="100%">
							<BarChart data={channels.slice(0, 10)}>
								<CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
								<XAxis
									dataKey="channel_name"
									stroke="hsl(var(--muted-foreground))"
									fontSize={10}
									tickFormatter={(value) => value.length > 10 ? `${value.substring(0, 10)}...` : value}
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
										borderRadius: '8px'
									}}
									cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
								/>
								<Bar dataKey="total_messages" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} name="Messages">
									{channels.map((entry, index) => (
										<Cell key={`cell-${index}`} fill={`hsl(var(--primary))`} />
									))}
								</Bar>
							</BarChart>
						</ResponsiveContainer>
					</CardContent>
				</Card>

				{/* Detailed List */}
				<div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
					{channels.map((channel, index) => (
						<Card key={channel.channel_id} className="bg-card/50 backdrop-blur-sm hover:border-primary/50 transition-colors">
							<CardHeader className="pb-3">
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2">
										<Badge variant="outline" className="h-6 w-6 flex items-center justify-center rounded-full p-0">
											{index + 1}
										</Badge>
										<CardTitle className="text-base font-medium truncate max-w-[150px]" title={channel.channel_name}>
											{channel.channel_name.startsWith('#') ? channel.channel_name : `#${channel.channel_name}`}
										</CardTitle>
									</div>
									<div className="flex items-center text-xs text-muted-foreground">
										<Users className="mr-1 h-3 w-3" />
										{channel.active_users}
									</div>
								</div>
							</CardHeader>
							<CardContent>
								<div className="space-y-4">
									<div className="flex items-center justify-between text-sm">
										<span className="text-muted-foreground flex items-center gap-1">
											<MessageSquare className="h-3 w-3" /> Messages
										</span>
										<span className="font-semibold">{channel.total_messages}</span>
									</div>

									{channel.top_user && (
										<div className="pt-3 border-t border-border/50">
											<p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
												<Crown className="h-3 w-3 text-yellow-500" /> Top Connector
											</p>
											<div className="flex items-center justify-between">
												<span className="font-medium text-sm">{channel.top_user.username}</span>
												<Badge variant="secondary" className="text-xs">
													{channel.top_user.message_count} msgs
												</Badge>
											</div>
										</div>
									)}
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			</div>
		</div>
	)
}
