import sys
import os
from pathlib import Path

# Add app directory to Python path
app_dir = Path(__file__).parent.parent
sys.path.append(str(app_dir))

import asyncio
import aiohttp
import time
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from app.models.research_models import ResearchMode, SportType

# Set Redis URL for testing
os.environ["REDIS_URL"] = "redis://localhost:6379"

# Constants
API_URL = "http://localhost:8000"
API_KEY = "3Qet_-y0LSkpIhp8rWhMOx0Cj-tyLLGGng56Yyuba_I"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

console = Console()

async def make_request(session, endpoint, method="GET", data=None, expected_status=200):
    """Make a request and return response time and status"""
    start_time = time.time()
    try:
        async with session.request(method, f"{API_URL}{endpoint}", 
                                 headers=HEADERS, 
                                 json=data) as response:
            text = await response.text()
            duration = time.time() - start_time
            
            # Debug headers
            console.print(f"\n[yellow]Response Headers for {endpoint}:[/yellow]")
            for k, v in response.headers.items():
                console.print(f"[dim]{k}: {v}[/dim]")
            
            # Debug response
            try:
                json_response = json.loads(text)
                console.print(f"\n[yellow]Response Body:[/yellow]")
                console.print(json_response)
            except:
                console.print(f"\n[yellow]Raw Response:[/yellow] {text}")
            
            return {
                "status": response.status,
                "duration": duration,
                "cache_hit": "X-Cache-Hit" in response.headers or "Redis-Cache-Hit" in response.headers,
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                "response": text
            }
    except Exception as e:
        console.print(f"[red]Error making request to {endpoint}: {str(e)}[/red]")
        return {
            "status": 500,
            "duration": time.time() - start_time,
            "error": str(e),
            "cache_hit": False,
            "rate_limit_remaining": None
        }

async def test_rate_limiting():
    """Test rate limiting by making rapid requests"""
    console.print("\n[bold blue]Testing Rate Limiting...[/bold blue]")
    
    async with aiohttp.ClientSession() as session:
        # Test research endpoint (30/minute limit)
        results = []
        total_requests = 40  # Should hit rate limit
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Making rapid requests...", total=total_requests)
            
            for i in range(total_requests):
                data = {
                    "query": "Should I bet on the Lakers tonight?",
                    "mode": ResearchMode.QUICK.value,
                    "context": {
                        "teams": ["Lakers"],
                        "sport": SportType.BASKETBALL.value
                    }
                }
                result = await make_request(session, "/research", "POST", data)
                results.append(result)
                progress.update(task, advance=1)
                
                # Print rate limit info
                remaining = result.get("rate_limit_remaining")
                if remaining:
                    console.print(f"[cyan]Requests remaining: {remaining}[/cyan]")
                
                if result["status"] == 429:
                    console.print("[red]Rate limit hit![/red]")
                    # Wait a bit before continuing to allow rate limit to reset
                    await asyncio.sleep(2)
                elif result["status"] == 500:
                    console.print(f"[red]Server error: {result.get('response', 'No error details')}[/red]")
                
                # Small delay between requests to not overwhelm server
                await asyncio.sleep(0.1)
        
        # Display results
        table = Table(title="Rate Limiting Test Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        successful = len([r for r in results if r["status"] == 200])
        rate_limited = len([r for r in results if r["status"] == 429])
        errors = len([r for r in results if r["status"] not in [200, 429]])
        
        table.add_row("Total Requests", str(len(results)))
        table.add_row("Successful Requests", str(successful))
        table.add_row("Rate Limited Requests", str(rate_limited))
        table.add_row("Error Requests", str(errors))
        
        console.print(table)
        
        return rate_limited > 0  # Test passes if we hit rate limit

async def test_caching():
    """Test caching by making duplicate requests"""
    console.print("\n[bold blue]Testing Caching...[/bold blue]")
    
    async with aiohttp.ClientSession() as session:
        results = []
        test_queries = [
            "Should I bet on the Lakers tonight?",
            "What are the odds for the Warriors game?",
            "Is Lebron James playing tonight?"
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Testing cache hits...", total=len(test_queries) * 2)
            
            for query in test_queries:
                # Make two identical requests
                for attempt in range(2):
                    data = {
                        "query": query, 
                        "mode": ResearchMode.QUICK.value,
                        "context": {
                            "teams": ["Lakers"],
                            "sport": SportType.BASKETBALL.value
                        }
                    }
                    result = await make_request(session, "/research", "POST", data)
                    results.append(result)
                    progress.update(task, advance=1)
                    
                    # Print cache info
                    if result.get("cache_hit"):
                        console.print(f"[green]Cache hit for query: {query}[/green]")
                    else:
                        console.print(f"[yellow]Cache miss for query: {query}[/yellow]")
                    
                    # Print any errors
                    if result["status"] != 200:
                        console.print(f"[red]Error: {result.get('response', 'No error details')}[/red]")
                    
                    await asyncio.sleep(1)  # Wait between requests
        
        # Display results
        table = Table(title="Cache Test Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        cache_hits = len([r for r in results if r.get("cache_hit", False)])
        cache_misses = len(results) - cache_hits
        avg_cache_miss = sum(r["duration"] for r in results if not r.get("cache_hit", False)) / cache_misses if cache_misses > 0 else 0
        avg_cache_hit = sum(r["duration"] for r in results if r.get("cache_hit", False)) / cache_hits if cache_hits > 0 else 0
        
        table.add_row("Total Requests", str(len(results)))
        table.add_row("Cache Hits", str(cache_hits))
        table.add_row("Cache Misses", str(cache_misses))
        table.add_row("Avg Response Time (Cache Miss)", f"{avg_cache_miss:.2f}s")
        table.add_row("Avg Response Time (Cache Hit)", f"{avg_cache_hit:.2f}s")
        
        console.print(table)
        
        return cache_hits > 0  # Test passes if we get any cache hits

async def monitor_cache_stats():
    """Monitor cache statistics during tests"""
    console.print("\n[bold blue]Cache Statistics...[/bold blue]")
    
    async with aiohttp.ClientSession() as session:
        before = await make_request(session, "/cache/stats")
        await asyncio.sleep(1)  # Wait for tests to complete
        after = await make_request(session, "/cache/stats")
        
        if before["status"] == 200 and after["status"] == 200:
            table = Table(title="Cache Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Before", style="yellow")
            table.add_column("After", style="green")
            
            try:
                before_data = json.loads(before.get("response", "{}"))
                after_data = json.loads(after.get("response", "{}"))
                
                # Redis stats
                redis_before = before_data.get("redis", {})
                redis_after = after_data.get("redis", {})
                
                table.add_row(
                    "Redis Status",
                    redis_before.get("status", "N/A"),
                    redis_after.get("status", "N/A")
                )
                table.add_row(
                    "Redis Keys",
                    str(redis_before.get("total_keys", "N/A")),
                    str(redis_after.get("total_keys", "N/A"))
                )
                table.add_row(
                    "Redis Memory Used",
                    str(redis_before.get("used_memory", "N/A")),
                    str(redis_after.get("used_memory", "N/A"))
                )
                
                # Memory cache stats
                memory_before = before_data.get("memory_cache", {})
                memory_after = after_data.get("memory_cache", {})
                
                table.add_row(
                    "Memory Cache Status",
                    memory_before.get("status", "N/A"),
                    memory_after.get("status", "N/A")
                )
                table.add_row(
                    "Memory Cache Keys",
                    str(memory_before.get("total_keys", "N/A")),
                    str(memory_after.get("total_keys", "N/A"))
                )
                
                console.print(table)
            except Exception as e:
                console.print(f"[red]Error parsing cache stats: {e}[/red]")

async def main():
    """Run all tests"""
    console.print("[bold green]Starting Load Tests...[/bold green]")
    
    try:
        # Test rate limiting
        rate_limit_passed = await test_rate_limiting()
        
        # Small delay to allow rate limits to reset
        console.print("\n[yellow]Waiting for rate limits to reset...[/yellow]")
        await asyncio.sleep(10)
        
        # Test caching
        cache_passed = await test_caching()
        
        # Monitor cache stats
        await monitor_cache_stats()
        
        # Final results
        console.print("\n[bold]Test Results Summary[/bold]")
        console.print(f"Rate Limiting Test: {'✅' if rate_limit_passed else '❌'}")
        console.print(f"Caching Test: {'✅' if cache_passed else '❌'}")
        
    except Exception as e:
        console.print(f"[red]Error during tests: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(main()) 