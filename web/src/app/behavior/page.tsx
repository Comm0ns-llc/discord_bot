'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface HeatmapCell {
	day_of_week: number
	hour_of_day: number
	message_count: number
	total_intensity: number
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const HOURS = Array.from({ length: 24 }, (_, i) => i)

export default function BehaviorPage() {
	const [heatmapData, setHeatmapData] = useState<HeatmapCell[]>([])
	const [isLoading, setIsLoading] = useState(true)
	const [error, setError] = useState<string | null>(null)
	const [maxIntensity, setMaxIntensity] = useState(1)

	useEffect(() => {
		async function fetchData() {
			const supabase = createClient()
			setIsLoading(true)
			setError(null)

			try {
				const { data, error: fetchError } = await supabase
					.from('analytics_hourly_heatmap')
					.select('*')

				if (fetchError) throw fetchError

				const cells = data || []
				setHeatmapData(cells)

				const max = Math.max(...cells.map(c => Number(c.total_intensity)), 1)
				setMaxIntensity(max)

			} catch (err) {
				console.error('Failed to fetch heatmap data:', err)
				setError(err instanceof Error ? err.message : 'Failed to fetch data')
			} finally {
				setIsLoading(false)
			}
		}

		fetchData()
	}, [])

	// Build a lookup map for quick access
	const dataMap = new Map<string, HeatmapCell>()
	heatmapData.forEach(cell => {
		dataMap.set(`${cell.day_of_week}-${cell.hour_of_day}`, cell)
	})

	function getIntensityColor(intensity: number): string {
		const ratio = intensity / maxIntensity
		// From deep slate to vibrant violet
		if (ratio === 0) return 'bg-muted/30'
		if (ratio < 0.2) return 'bg-violet-900/40'
		if (ratio < 0.4) return 'bg-violet-700/60'
		if (ratio < 0.6) return 'bg-violet-600/70'
		if (ratio < 0.8) return 'bg-violet-500/80'
		return 'bg-violet-400'
	}

	if (isLoading) {
		return (
			<div className="flex items-center justify-center h-96">
				<div className="animate-pulse text-muted-foreground">Loading behavior data...</div>
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
				<h1 className="text-3xl font-bold tracking-tight">Behavior</h1>
				<p className="text-muted-foreground">When is the community most active?</p>
			</div>

			<Card className="bg-card/50 backdrop-blur-sm">
				<CardHeader>
					<CardTitle>Activity Heatmap</CardTitle>
					<CardDescription>
						Darker colors = higher engagement. Find the best time for announcements!
					</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="overflow-x-auto">
						<div className="min-w-[600px]">
							{/* Hour labels */}
							<div className="flex ml-12 mb-2">
								{HOURS.map(hour => (
									<div key={hour} className="w-8 text-center text-xs text-muted-foreground">
										{hour}
									</div>
								))}
							</div>

							{/* Grid */}
							{DAYS.map((day, dayIndex) => (
								<div key={day} className="flex items-center mb-1">
									<div className="w-12 text-sm text-muted-foreground font-medium">{day}</div>
									{HOURS.map(hour => {
										const cell = dataMap.get(`${dayIndex}-${hour}`)
										const intensity = cell ? Number(cell.total_intensity) : 0
										const messages = cell ? Number(cell.message_count) : 0

										return (
											<div
												key={hour}
												className={`w-8 h-8 rounded-sm ${getIntensityColor(intensity)} 
                          transition-all hover:scale-110 hover:z-10 cursor-pointer
                          flex items-center justify-center`}
												title={`${day} ${hour}:00 - ${messages} messages, ${intensity.toFixed(0)} score`}
											>
												{intensity > 0 && intensity / maxIntensity > 0.3 && (
													<span className="text-[10px] text-white/80">{messages}</span>
												)}
											</div>
										)
									})}
								</div>
							))}

							{/* Legend */}
							<div className="flex items-center gap-2 mt-6 text-xs text-muted-foreground">
								<span>Less</span>
								<div className="flex gap-1">
									<div className="w-4 h-4 rounded-sm bg-muted/30"></div>
									<div className="w-4 h-4 rounded-sm bg-violet-900/40"></div>
									<div className="w-4 h-4 rounded-sm bg-violet-700/60"></div>
									<div className="w-4 h-4 rounded-sm bg-violet-600/70"></div>
									<div className="w-4 h-4 rounded-sm bg-violet-500/80"></div>
									<div className="w-4 h-4 rounded-sm bg-violet-400"></div>
								</div>
								<span>More</span>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</div>
	)
}
