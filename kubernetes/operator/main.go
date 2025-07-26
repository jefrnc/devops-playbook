package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/robfig/cron/v3"
	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	_ "k8s.io/client-go/plugin/pkg/client/auth"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"

	metricsv1 "github.com/jefrnc/dora-operator/api/v1"
	"github.com/jefrnc/dora-operator/controllers"
)

var (
	scheme   = runtime.NewScheme()
	setupLog = ctrl.Log.WithName("setup")
)

func init() {
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(metricsv1.AddToScheme(scheme))
}

func main() {
	var metricsAddr string
	var enableLeaderElection bool
	var probeAddr string
	flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "The address the metric endpoint binds to.")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "The address the probe endpoint binds to.")
	flag.BoolVar(&enableLeaderElection, "leader-elect", false,
		"Enable leader election for controller manager. "+
			"Enabling this will ensure there is only one active controller manager.")
	opts := zap.Options{
		Development: true,
	}
	opts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&opts)))

	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
		Scheme:                 scheme,
		MetricsBindAddress:     metricsAddr,
		Port:                   9443,
		HealthProbeBindAddress: probeAddr,
		LeaderElection:         enableLeaderElection,
		LeaderElectionID:       "dora-metrics-operator",
	})
	if err != nil {
		setupLog.Error(err, "unable to start manager")
		os.Exit(1)
	}

	// Create metrics collector
	collector := &MetricsCollector{
		Client: mgr.GetClient(),
		Scheme: mgr.GetScheme(),
		Cron:   cron.New(),
	}

	// Setup controller
	if err = (&controllers.DORAMetricReconciler{
		Client:    mgr.GetClient(),
		Scheme:    mgr.GetScheme(),
		Collector: collector,
	}).SetupWithManager(mgr); err != nil {
		setupLog.Error(err, "unable to create controller", "controller", "DORAMetric")
		os.Exit(1)
	}

	// Add health checks
	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		setupLog.Error(err, "unable to set up health check")
		os.Exit(1)
	}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		setupLog.Error(err, "unable to set up ready check")
		os.Exit(1)
	}

	setupLog.Info("starting manager")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		setupLog.Error(err, "problem running manager")
		os.Exit(1)
	}
}

// MetricsCollector handles the actual metric collection
type MetricsCollector struct {
	Client runtime.Client
	Scheme *runtime.Scheme
	Cron   *cron.Cron
}

// CollectMetrics collects metrics based on the DORAMetric spec
func (mc *MetricsCollector) CollectMetrics(ctx context.Context, dm *metricsv1.DORAMetric) error {
	for _, metric := range dm.Spec.Metrics {
		if !metric.Enabled {
			continue
		}

		// Schedule metric collection
		_, err := mc.Cron.AddFunc(metric.Schedule, func() {
			if err := mc.collectSingleMetric(ctx, dm, metric); err != nil {
				setupLog.Error(err, "failed to collect metric",
					"metric", metric.Name,
					"dorametric", dm.Name)
			}
		})
		if err != nil {
			return fmt.Errorf("failed to schedule metric %s: %w", metric.Name, err)
		}
	}

	mc.Cron.Start()
	return nil
}

func (mc *MetricsCollector) collectSingleMetric(ctx context.Context, dm *metricsv1.DORAMetric, metric metricsv1.MetricConfig) error {
	var value float64
	var err error

	switch metric.Name {
	case "deployment-frequency":
		value, err = mc.collectDeploymentFrequency(ctx, dm)
	case "lead-time":
		value, err = mc.collectLeadTime(ctx, dm)
	case "mttr":
		value, err = mc.collectMTTR(ctx, dm)
	case "change-failure-rate":
		value, err = mc.collectChangeFailureRate(ctx, dm)
	default:
		return fmt.Errorf("unknown metric: %s", metric.Name)
	}

	if err != nil {
		// Update status with error
		dm.Status.Metrics[metric.Name] = metricsv1.MetricStatus{
			Error:     err.Error(),
			Timestamp: time.Now().Format(time.RFC3339),
		}
		return err
	}

	// Update status with value
	if dm.Status.Metrics == nil {
		dm.Status.Metrics = make(map[string]metricsv1.MetricStatus)
	}

	dm.Status.Metrics[metric.Name] = metricsv1.MetricStatus{
		Value:     value,
		Timestamp: time.Now().Format(time.RFC3339),
	}
	dm.Status.LastCollection = time.Now().Format(time.RFC3339)

	// Export to Prometheus if enabled
	if dm.Spec.Export.Prometheus.Enabled {
		if err := mc.exportToPrometheus(dm, metric.Name, value); err != nil {
			setupLog.Error(err, "failed to export to prometheus")
		}
	}

	// Send webhook if enabled
	if dm.Spec.Export.Webhook.Enabled {
		if err := mc.sendWebhook(dm, metric.Name, value); err != nil {
			setupLog.Error(err, "failed to send webhook")
		}
	}

	return nil
}

func (mc *MetricsCollector) collectDeploymentFrequency(ctx context.Context, dm *metricsv1.DORAMetric) (float64, error) {
	// Implementation would call the actual metric collection logic
	// This is a placeholder
	return 5.2, nil
}

func (mc *MetricsCollector) collectLeadTime(ctx context.Context, dm *metricsv1.DORAMetric) (float64, error) {
	// Implementation would call the actual metric collection logic
	return 18.5, nil
}

func (mc *MetricsCollector) collectMTTR(ctx context.Context, dm *metricsv1.DORAMetric) (float64, error) {
	// Implementation would call the actual metric collection logic
	return 45.3, nil
}

func (mc *MetricsCollector) collectChangeFailureRate(ctx context.Context, dm *metricsv1.DORAMetric) (float64, error) {
	// Implementation would call the actual metric collection logic
	return 12.5, nil
}

func (mc *MetricsCollector) exportToPrometheus(dm *metricsv1.DORAMetric, metricName string, value float64) error {
	// Export metric to Prometheus
	// This would use prometheus client library
	return nil
}

func (mc *MetricsCollector) sendWebhook(dm *metricsv1.DORAMetric, metricName string, value float64) error {
	// Send webhook notification
	// This would make HTTP request to configured webhook URL
	return nil
}
