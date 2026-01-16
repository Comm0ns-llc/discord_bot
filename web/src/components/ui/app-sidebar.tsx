'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import {
	LayoutDashboard,
	Activity,
	Users,
	Clock,
	GitGraph,
	Heart,
	MessageSquare
} from 'lucide-react'

const navigation = [
	{ name: 'Home', href: '/', icon: LayoutDashboard },
	{ name: 'Channels', href: '/channels', icon: MessageSquare }, // Added Channels
	{ name: 'Realtime', href: '/realtime', icon: Activity },
	{
		name: 'Engagement',
		href: '/engagement',
		icon: Users,
		children: [
			{ name: 'Social Graph', href: '/engagement/graph', icon: GitGraph },
			{ name: 'Leaderboard', href: '/engagement/leaderboard', icon: Users },
		]
	},
	{ name: 'Behavior', href: '/behavior', icon: Clock },
	{ name: 'Retention', href: '/retention', icon: GitGraph }, // Using GitGraph for cohort as placeholder
	{ name: 'Sentiment', href: '/sentiment', icon: Heart },
]

export function AppSidebar() {
	const pathname = usePathname()

	return (
		<div className="flex flex-col w-64 border-r bg-card h-screen sticky top-0">
			<div className="p-6 border-b">
				<h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
					Comm0ns<br />Analytics
				</h1>
			</div>

			<nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
				{navigation.map((item) => {
					const isActive = pathname === item.href

					return (
						<div key={item.name}>
							{!item.children ? (
								<Link
									href={item.href}
									className={cn(
										"flex items-center px-4 py-3 text-sm font-medium rounded-md transition-colors",
										isActive
											? "bg-primary/10 text-primary"
											: "text-muted-foreground hover:bg-muted hover:text-foreground"
									)}
								>
									<item.icon className="mr-3 h-5 w-5" />
									{item.name}
								</Link>
							) : (
								<div className="space-y-1">
									<div className="px-4 py-2 text-xs font-semibold text-muted-foreground/70 uppercase tracking-wider">
										{item.name}
									</div>
									{item.children.map((child) => {
										const isChildActive = pathname === child.href
										return (
											<Link
												key={child.name}
												href={child.href}
												className={cn(
													"flex items-center px-4 py-2 pl-8 text-sm font-medium rounded-md transition-colors",
													isChildActive
														? "bg-primary/10 text-primary"
														: "text-muted-foreground hover:bg-muted hover:text-foreground"
												)}
											>
												<child.icon className="mr-3 h-4 w-4" />
												{child.name}
											</Link>
										)
									})}
								</div>
							)}
						</div>
					)
				})}
			</nav>

			<div className="p-4 border-t bg-muted/20">
				<p className="text-xs text-center text-muted-foreground">
					v0.1.0 Beta
				</p>
			</div>
		</div>
	)
}
