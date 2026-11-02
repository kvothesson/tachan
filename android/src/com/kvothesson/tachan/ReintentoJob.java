package com.kvothesson.tachan;

import android.app.NotificationManager;
import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

/** Vuelve a probar la cola cuando hay wifi, con la espera creciente que maneja Android. */
public class ReintentoJob extends JobService {
    private static final int ID = 1;

    static void programar(Context c) {
        JobInfo trabajo = new JobInfo.Builder(ID, new ComponentName(c, ReintentoJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                .setPersisted(true)
                .build();
        c.getSystemService(JobScheduler.class).schedule(trabajo);
    }

    @Override
    public boolean onStartJob(final JobParameters parametros) {
        new Thread(() -> {
            boolean listo = Cola.procesar(getApplicationContext());
            if (listo) getSystemService(NotificationManager.class).cancel(EnvioServicio.NOTI_RESULTADO);
            jobFinished(parametros, !listo);
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters parametros) {
        return true;
    }
}
