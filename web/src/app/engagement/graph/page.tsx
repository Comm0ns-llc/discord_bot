'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import dynamic from 'next/dynamic'

// Dynamically import ForceGraph2D to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false })

interface GraphNode {
	id: string
	name: string
	val: number
	x?: number
	y?: number
}

interface GraphLink {
	source: string
	target: string
	value: number
}

interface GraphData {
	nodes: GraphNode[]
	links: GraphLink[]
}

interface SocialGraphRow {
	source_user: number
	target_user: number
	weight: number
}

export default function SocialGraphPage() {
	const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
	const [isLoading, setIsLoading] = useState(true)
	const [error, setError] = useState<string | null>(null)
	const graphRef = useRef<HTMLDivElement>(null)
	const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

	// Handle resize
	useEffect(() => {
		function handleResize() {
			if (graphRef.current) {
				setDimensions({
					width: graphRef.current.offsetWidth,
					height: 600
				})
			}
		}
		handleResize()
		window.addEventListener('resize', handleResize)
		return () => window.removeEventListener('resize', handleResize)
	}, [])

	useEffect(() => {
		async function fetchData() {
			const supabase = createClient()
			setIsLoading(true)
			setError(null)

			try {
				// Fetch social graph data
				const { data: graphRows, error: graphError } = await supabase
					.from('analytics_social_graph')
					.select('*')
					.order('weight', { ascending: false })
					.limit(200) // Limit for performance

				if (graphError) throw graphError

				// Fetch usernames
				const { data: users, error: usersError } = await supabase
					.from('users')
					.select('user_id, username')

				if (usersError) throw usersError

				const userMap = new Map(users?.map(u => [String(u.user_id), u.username]) || [])

				// Build graph data
				const nodeSet = new Set<string>()
				const nodeWeights = new Map<string, number>()
				const links: GraphLink[] = []

				graphRows?.forEach((row: SocialGraphRow) => {
					const sourceId = String(row.source_user)
					const targetId = String(row.target_user)

					nodeSet.add(sourceId)
					nodeSet.add(targetId)

					// Accumulate weights for node sizing
					nodeWeights.set(sourceId, (nodeWeights.get(sourceId) || 0) + row.weight)
					nodeWeights.set(targetId, (nodeWeights.get(targetId) || 0) + row.weight)

					links.push({
						source: sourceId,
						target: targetId,
						value: row.weight
					})
				})

				const nodes: GraphNode[] = Array.from(nodeSet).map(id => ({
					id,
					name: userMap.get(id) || `User ${id.slice(-4)}`,
					val: Math.sqrt(nodeWeights.get(id) || 1) * 2
				}))

				setGraphData({ nodes, links })

			} catch (err) {
				console.error('Failed to fetch graph data:', err)
				setError(err instanceof Error ? err.message : 'Failed to fetch data')
			} finally {
				setIsLoading(false)
			}
		}

		fetchData()
	}, [])

	const nodeCanvasObject = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
		const label = node.name
		const fontSize = 12 / globalScale
		ctx.font = `${fontSize}px Inter, sans-serif`

		// Node circle
		ctx.beginPath()
		ctx.arc(node.x || 0, node.y || 0, node.val, 0, 2 * Math.PI, false)
		ctx.fillStyle = 'hsl(264, 80%, 60%)'
		ctx.fill()

		// Label
		ctx.textAlign = 'center'
		ctx.textBaseline = 'middle'
		ctx.fillStyle = 'white'
		if (globalScale > 0.5) {
			ctx.fillText(label, node.x || 0, (node.y || 0) + node.val + fontSize + 2)
		}
	}, [])

	if (isLoading) {
		return (
			<div className="flex items-center justify-center h-96">
				<div className="animate-pulse text-muted-foreground">Loading social graph...</div>
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
				<h1 className="text-3xl font-bold tracking-tight">Social Graph</h1>
				<p className="text-muted-foreground">Visualizing member connections through reactions</p>
			</div>

			<Card className="bg-card/50 backdrop-blur-sm">
				<CardHeader>
					<CardTitle>Connection Network</CardTitle>
					<CardDescription>
						Links show who reacts to whose messages. Larger nodes = more interactions.
					</CardDescription>
				</CardHeader>
				<CardContent ref={graphRef}>
					{graphData.nodes.length > 0 ? (
						<ForceGraph2D
							graphData={graphData as any}
							width={dimensions.width}
							height={dimensions.height}
							nodeLabel="name"
							nodeAutoColorBy="id"
							nodeVal="val"
							linkWidth={(link: any) => Math.sqrt(link.value || 1)}
							linkColor={() => 'rgba(136, 132, 216, 0.4)'}
							cooldownTicks={100}
						/>
					) : (
						<div className="flex items-center justify-center h-96 text-muted-foreground">
							No interaction data available yet. Start reacting to messages!
						</div>
					)}
				</CardContent>
			</Card>
		</div>
	)
}
