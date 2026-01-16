'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table"
import { Badge } from '@/components/ui/badge'

interface LeaderboardEntry {
	user_id: number
	username: string
	current_score: number
	weekly_score: number
	total_messages: number
}

function getMedal(rank: number): string {
	if (rank === 1) return '🥇'
	if (rank === 2) return '🥈'
	if (rank === 3) return '🥉'
	return `#${rank}`
}

export default function LeaderboardPage() {
	const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([])
	const [isLoading, setIsLoading] = useState(true)
	const [error, setError] = useState<string | null>(null)

	useEffect(() => {
		async function fetchData() {
			const supabase = createClient()
			setIsLoading(true)
			setError(null)

			try {
				const { data, error: fetchError } = await supabase
					.from('analytics_leaderboard')
					.select('*')
					.order('current_score', { ascending: false })
					.limit(50)

				if (fetchError) throw fetchError
				setLeaderboard(data || [])

			} catch (err) {
				console.error('Failed to fetch leaderboard:', err)
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
				<div className="animate-pulse text-muted-foreground">Loading leaderboard...</div>
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
		<div className="space-y-6">
			<div>
				<h1 className="text-3xl font-bold tracking-tight">Leaderboard</h1>
				<p className="text-muted-foreground">Top contributors ranked by total engagement score</p>
			</div>

			<Card className="bg-card/50 backdrop-blur-sm">
				<CardHeader>
					<CardTitle>All-Time Rankings</CardTitle>
					<CardDescription>Top 50 members by cumulative score</CardDescription>
				</CardHeader>
				<CardContent>
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead className="w-[80px]">Rank</TableHead>
								<TableHead>Username</TableHead>
								<TableHead className="text-right">Messages</TableHead>
								<TableHead className="text-right">Weekly Score</TableHead>
								<TableHead className="text-right">Total Score</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{leaderboard.map((user, index) => (
								<TableRow key={user.user_id} className={index < 3 ? 'bg-primary/5' : ''}>
									<TableCell>
										<Badge
											variant={index < 3 ? "default" : "secondary"}
											className={
												index === 0 ? "bg-yellow-500/80 text-white" :
													index === 1 ? "bg-gray-400/80 text-white" :
														index === 2 ? "bg-orange-600/80 text-white" : ""
											}
										>
											{getMedal(index + 1)}
										</Badge>
									</TableCell>
									<TableCell className="font-medium">{user.username}</TableCell>
									<TableCell className="text-right text-muted-foreground">
										{user.total_messages.toLocaleString()}
									</TableCell>
									<TableCell className="text-right">
										<span className="text-green-500">{Number(user.weekly_score).toFixed(1)}</span>
									</TableCell>
									<TableCell className="text-right font-semibold">
										{Number(user.current_score).toFixed(1)}
									</TableCell>
								</TableRow>
							))}
							{leaderboard.length === 0 && (
								<TableRow>
									<TableCell colSpan={5} className="text-center text-muted-foreground py-8">
										No data yet. Start sending messages!
									</TableCell>
								</TableRow>
							)}
						</TableBody>
					</Table>
				</CardContent>
			</Card>
		</div>
	)
}
