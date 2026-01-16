# Comm0ns Analytics Dashboard

Comm0nsコミュニティの活動を可視化・分析するためのWebダッシュボードです。
Discord Botが集めたデータをかっこよく表示します。

## デザイン方針

**"Cool, Advanced, & Engaging"**
- **没入感**: ユーザーが見ていてワクワクするような、近未来的または洗練されたUIを目指します。
- **インタラクティブ**: 静的なグラフだけでなく、触って動かせる要素を取り入れます。
- **カスタマイズ性**: 将来的にはGoogle Analyticsのように、ユーザーが見たい軸でデータを分析できる自由度を持たせます。

## 開発の始め方

### 1. 依存関係のインストール

```bash
npm install
# or
yarn install
```

### 2. コンポーネントの追加 (shadcn/ui)

UIコンポーネントには `shadcn/ui` を使用しています。新しいパーツが必要な場合は以下のように追加してください。

```bash
npx shadcn@latest add [component-name]
# 例: npx shadcn@latest add chart
```

### 3. 開発サーバーの起動

```bash
npm run dev
```

[http://localhost:3000](http://localhost:3000) を開き、データが表示されることを確認してください。
（Discord BotがDBにデータを書き込んでいる必要があります）

## 技術スタック

- **Framework**: Next.js (App Router)
- **Styling**: Tailwind CSS, CSS Modules (for custom animations)
- **UI Library**: shadcn/ui, Radix UI
- **Charting**: Recharts
- **Icons**: Lucide React
- **Database**: Supabase
