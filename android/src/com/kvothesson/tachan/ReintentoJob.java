package com.kvothesson.tachan;

import android.app.NotificationManager;
import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

/** Vuelve a probar la cola cuando hay wifi. */
public class ReintentoJob extends JobService {
    private static final int ID = 1;
    private static final int ID_AHORA = 2;

    // El celu no se entera de que la compu se prendió: prueba cada vez más espaciado. Con la espera doble de
    // Android, tras unas horas apagada pasaban hasta 5 horas entre intentos; así suma un minuto por intento.
    static void programar(Context c) {
        JobInfo trabajo = new JobInfo.Builder(ID, new ComponentName(c, ReintentoJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                .setBackoffCriteria(60_000, JobInfo.BACKOFF_POLICY_LINEAR)
                .setPersisted(true)
                .build();
        c.getSystemService(JobScheduler.class).schedule(trabajo);
    }

    /** Un intento ya, al abrir la app o cuando algo llegó a una compu. No toca el reintento de fondo, que quizás está mandando. */
    static void ahora(Context c) {
        if (!Cola.hayPendientes(c)) return;
        JobInfo trabajo = new JobInfo.Builder(ID_AHORA, new ComponentName(c, ReintentoJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                .build();
        c.getSystemService(JobScheduler.class).schedule(trabajo);
    }

    static void cancelar(Context c) {
        c.getSystemService(JobScheduler.class).cancel(ID);
        c.getSystemService(JobScheduler.class).cancel(ID_AHORA);
    }

    @Override
    public boolean onStartJob(final JobParameters parametros) {
        new Thread(() -> {
            boolean listo = Cola.procesar(getApplicationContext());
            if (listo) getSystemService(NotificationManager.class).cancel(EnvioServicio.NOTI_RESULTADO);
            jobFinished(parametros, !listo && parametros.getJobId() == ID);
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters parametros) {
        return parametros.getJobId() == ID;
    }
}
