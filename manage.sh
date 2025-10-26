#!/bin/bash

# Woodsgate Master Management Script
# Manages both data collector and web GUI services

case "$1" in
    start)
        echo "Starting Woodsgate services..."
        docker compose up -d
        echo "Services started. Use './manage.sh logs' to view logs."
        ;;
    stop)
        echo "Stopping Woodsgate services..."
        docker compose down
        ;;
    restart)
        echo "Restarting Woodsgate services..."
        docker compose restart
        ;;
    logs)
        if [ -z "$2" ]; then
            echo "Showing logs for all services (Press Ctrl+C to exit)..."
            docker compose logs -f
        else
            echo "Showing logs for $2 (Press Ctrl+C to exit)..."
            docker compose logs -f "$2"
        fi
        ;;
    build)
        echo "Building all containers..."
        docker compose build --no-cache
        ;;
    status)
        echo "Services status:"
        docker compose ps
        ;;
    collector)
        case "$2" in
            logs)
                echo "Showing collector logs..."
                docker compose logs -f woodsgate-collector
                ;;
            shell)
                echo "Opening shell in collector container..."
                docker compose exec woodsgate-collector /bin/bash
                ;;
            restart)
                echo "Restarting collector..."
                docker compose restart woodsgate-collector
                ;;
            *)
                echo "Usage: $0 collector {logs|shell|restart}"
                ;;
        esac
        ;;
    webgui)
        case "$2" in
            logs)
                echo "Showing webgui logs..."
                docker compose logs -f webgui
                ;;
            shell)
                echo "Opening shell in webgui container..."
                docker compose exec webgui /bin/bash
                ;;
            restart)
                echo "Restarting webgui..."
                docker compose restart webgui
                ;;
            *)
                echo "Usage: $0 webgui {logs|shell|restart}"
                ;;
        esac
        ;;
    *)
        echo "Woodsgate Management Script"
        echo "Usage: $0 {start|stop|restart|logs|build|status|collector|webgui}"
        echo ""
        echo "Main commands:"
        echo "  start    - Start both collector and webgui services"
        echo "  stop     - Stop both services"  
        echo "  restart  - Restart both services"
        echo "  logs     - View logs (optional: specify service name)"
        echo "  build    - Rebuild all container images"
        echo "  status   - Show status of all services"
        echo ""
        echo "Service-specific commands:"
        echo "  collector logs     - Show only collector logs"
        echo "  collector shell    - Open shell in collector container"
        echo "  collector restart  - Restart only collector"
        echo "  webgui logs        - Show only webgui logs"
        echo "  webgui shell       - Open shell in webgui container"
        echo "  webgui restart     - Restart only webgui"
        echo ""
        echo "Examples:"
        echo "  $0 start                # Start everything"
        echo "  $0 logs webgui         # Show only web GUI logs"
        echo "  $0 collector logs      # Show only collector logs"
        exit 1
        ;;
esac